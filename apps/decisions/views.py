from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

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

def is_reviewer(user):
    return any(user_has_role(user, role) for role in REVIEWER_ROLES)

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
        Consultant.objects.filter(status="vetted")
        .select_related("user")
        .order_by("full_name")
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
