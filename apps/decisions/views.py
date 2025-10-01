from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction

from apps.consultants.models import Consultant
from apps.certificates.services import (
    generate_approval_certificate,
    generate_rejection_letter,
)
from .forms import ActionForm
from .models import ApplicationAction

REVIEWER_GROUPS = {
    'BackOffice',
    'DISAgents',
    'BoardCommittee',
    'SeniorImmigration',
    'Admins',
}

def is_reviewer(user):
    if not user.is_authenticated:
        return False
    # superusers always allowed
    if user.is_superuser:
        return True
    # group membership check
    return user.groups.filter(name__in=REVIEWER_GROUPS).exists()

def reviewer_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_reviewer(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)


@reviewer_required
def decisions_dashboard(request):
    """Dashboard for reviewers to see vetted applications and record actions."""

    consultants = (
        Consultant.objects.filter(status__in=["vetted", "approved", "rejected"])
        .select_related("user")
        .order_by("full_name")
    )

    form = ActionForm()

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        form = ActionForm(request.POST)

        if consultant_id and form.is_valid():
            consultant = get_object_or_404(Consultant, pk=consultant_id)
            action_obj = form.save(commit=False)
            action_obj.consultant = consultant
            action_obj.actor = request.user
            action_obj.save()

            update_fields = ["status"]

            if action_obj.action == "vetted":
                new_status = "vetted"
            elif action_obj.action == "approved":
                generate_approval_certificate(
                    consultant,
                    generated_by=action_obj.actor.get_full_name()
                    or action_obj.actor.username,
                )
                new_status = "approved"
                update_fields.extend(
                    [
                        "certificate_pdf",
                        "certificate_generated_at",
                        "rejection_letter",
                        "rejection_letter_generated_at",
                    ]
                )
            elif action_obj.action == "rejected":
                generate_rejection_letter(
                    consultant,
                    generated_by=action_obj.actor.get_full_name()
                    or action_obj.actor.username,
                )
                new_status = "rejected"
                update_fields.extend(
                    [
                        "rejection_letter",
                        "rejection_letter_generated_at",
                        "certificate_pdf",
                        "certificate_generated_at",
                    ]
                )
            else:
                new_status = consultant.status

            consultant.status = new_status
            consultant.save(update_fields=update_fields)

            messages.success(
                request,
                f"Application {consultant.full_name} marked as {new_status}.",
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
        action_obj = form.save(commit=False)
        action_obj.consultant = application
        action_obj.actor = request.user
        action_obj.save()

        # Update the application's status based on action
        update_fields = ['status']

        if action_obj.action == 'vetted':
            new_status = 'vetted'
        elif action_obj.action == 'approved':
            generate_approval_certificate(
                application,
                generated_by=action_obj.actor.get_full_name() or action_obj.actor.username,
            )
            new_status = 'approved'
            update_fields.extend([
                'certificate_pdf',
                'certificate_generated_at',
                'rejection_letter',
                'rejection_letter_generated_at',
            ])
        elif action_obj.action == 'rejected':
            generate_rejection_letter(
                application,
                generated_by=action_obj.actor.get_full_name() or action_obj.actor.username,
            )
            new_status = 'rejected'
            update_fields.extend([
                'rejection_letter',
                'rejection_letter_generated_at',
                'certificate_pdf',
                'certificate_generated_at',
            ])
        else:
            new_status = application.status  # fallback

        application.status = new_status
        application.save(update_fields=update_fields)

        messages.success(request, f"Application {application.full_name} marked as {new_status}.")
        return redirect('officer_application_detail', pk=application.pk)

    # recent actions for audit trail
    recent_actions = application.actions.select_related('actor')[:20]

    return render(request, 'officer/application_detail.html', {
        'application': application,
        'form': form,
        'recent_actions': recent_actions,
    })
