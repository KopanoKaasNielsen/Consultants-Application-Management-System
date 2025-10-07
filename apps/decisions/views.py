from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.certificates.forms import CertificateRenewalDecisionForm
from apps.certificates.models import CertificateRenewal
from apps.consultants.models import Consultant
from .forms import ActionForm
from .services import process_decision_action
from apps.users.constants import UserRole as Roles
from apps.users.permissions import user_has_role

ACTION_MESSAGES = {
    "vetted": "Application has been vetted.",
    "approved": "Application approved.",
    "rejected": "Application has been rejected.",
}

REVIEWER_ROLES = (Roles.BOARD, Roles.STAFF)


def _extract_roles(subject):
    if hasattr(subject, "jwt_roles"):
        return getattr(subject, "jwt_roles"), getattr(
            subject, "jwt_token_present", False
        )

    if hasattr(subject, "user") and hasattr(subject.user, "jwt_roles"):
        return getattr(subject.user, "jwt_roles"), getattr(
            subject.user, "jwt_token_present", False
        )

    return None, False


def is_reviewer(subject):
    roles, token_present = _extract_roles(subject)
    if roles is not None:
        if any(role in roles for role in REVIEWER_ROLES):
            return True
        if token_present or roles:
            return False

    user = getattr(subject, "user", subject)
    return any(user_has_role(user, role) for role in REVIEWER_ROLES)

def reviewer_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_reviewer(request):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)


@reviewer_required
def decisions_dashboard(request):
    """Dashboard for reviewers to see submitted/vetted applications and record actions."""

    consultants = (
        Consultant.objects.filter(status__in=["submitted", "vetted"])
        .select_related("user")
        .order_by("status", "-submitted_at", "full_name")
    )

    form = ActionForm()

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        form = ActionForm(request.POST)

        if consultant_id and form.is_valid():
            consultant = get_object_or_404(Consultant, pk=consultant_id)
            action = form.cleaned_data["action"]
            notes = form.cleaned_data.get("notes", "")

            process_decision_action(
                consultant,
                action,
                request.user,
                notes=notes,
            )

            messages.success(
                request,
                ACTION_MESSAGES.get(action, "Application updated."),
            )
            return redirect("decisions_dashboard")

    return render(
        request,
        "officer/decisions_dashboard.html",
        {"consultants": consultants, "form": form},
    )


@reviewer_required
def applications_list(request):
    """
    Staff list of applications. Defaults to 'submitted' and 'vetted'.
    Add ?status=draft/submitted/vetted/approved/rejected to filter.
    """
    status = request.GET.get('status')
    qs = Consultant.objects.all().select_related('user').order_by('-submitted_at')

    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=['submitted', 'vetted'])

    return render(request, 'officer/applications_list.html', {
        'applications': qs,
        'active_status': status or 'submitted,vetted',
    })


@reviewer_required
@transaction.atomic
def application_detail(request, pk):
    """
    Shows an application's details + documents and lets reviewer take an action.
    """
    application = get_object_or_404(Consultant, pk=pk)
    form = ActionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        action = form.cleaned_data["action"]
        notes = form.cleaned_data.get("notes", "")

        process_decision_action(
            application,
            action,
            request.user,
            notes=notes,
        )

        messages.success(
            request, ACTION_MESSAGES.get(action, "Application updated.")
        )
        return redirect('officer_application_detail', pk=application.pk)

    # recent actions for audit trail
    recent_actions = application.actions.select_related('actor')[:20]

    return render(request, 'officer/application_detail.html', {
        'application': application,
        'form': form,
        'recent_actions': recent_actions,
    })


@reviewer_required
def renewal_requests(request):
    renewals = (
        CertificateRenewal.objects.select_related("consultant", "consultant__user")
        .order_by("status", "-requested_at")
    )

    pending_renewals = [
        renewal for renewal in renewals if renewal.status == CertificateRenewal.Status.PENDING
    ]
    processed_renewals = [
        renewal for renewal in renewals if renewal.status != CertificateRenewal.Status.PENDING
    ]

    active_form_target = None
    blank_form = CertificateRenewalDecisionForm()
    form = blank_form

    if request.method == "POST":
        renewal_id = request.POST.get("renewal_id")
        active_form_target = get_object_or_404(CertificateRenewal, pk=renewal_id)

        if active_form_target.status != CertificateRenewal.Status.PENDING:
            messages.error(request, "This renewal request has already been processed.")
        else:
            form = CertificateRenewalDecisionForm(request.POST)
            if form.is_valid():
                decision = form.cleaned_data["decision"]
                notes = form.cleaned_data.get("notes", "")
                actor_display = request.user.get_full_name() or request.user.username

                active_form_target.notes = notes
                active_form_target.processed_at = timezone.now()
                active_form_target.processed_by = actor_display

                if decision == CertificateRenewalDecisionForm.DECISION_APPROVE:
                    active_form_target.status = CertificateRenewal.Status.APPROVED

                    def queue_generation():
                        from apps.decisions.tasks import generate_approval_certificate_task

                        generate_approval_certificate_task.delay(
                            active_form_target.consultant.pk, actor_display
                        )

                    transaction.on_commit(queue_generation)
                    messages.success(
                        request,
                        "Renewal approved. A new certificate will be generated.",
                    )
                else:
                    active_form_target.status = CertificateRenewal.Status.DENIED
                    messages.info(request, "Renewal request denied.")

                active_form_target.save(
                    update_fields=[
                        "status",
                        "notes",
                        "processed_at",
                        "processed_by",
                    ]
                )
                return redirect("certificate_renewal_requests")

    return render(
        request,
        "officer/renewal_requests.html",
        {
            "pending_renewals": pending_renewals,
            "processed_renewals": processed_renewals,
            "form": form,
            "blank_form": blank_form,
            "active_form_target": active_form_target,
        },
    )
