from django.shortcuts import get_object_or_404, redirect, render

from apps.consultants.models import Consultant
from apps.decisions.models import ApplicationAction
from apps.decisions.services import process_decision_action
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required


@role_required(Roles.STAFF)
def vetting_dashboard(request):
    """Display consultant applications for vetting staff to review."""

    consultants = Consultant.objects.all().order_by("full_name")

    allowed_actions = {
        action: label
        for action, label in ApplicationAction.ACTION_CHOICES
        if action in {"vetted", "rejected"}
    }

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        action = request.POST.get("action")

        if consultant_id and action in allowed_actions:
            consultant = get_object_or_404(Consultant, pk=consultant_id)
            process_decision_action(consultant, action, request.user)
            return redirect("vetting_dashboard")

    return render(
        request,
        "vetting/dashboard.html",
        {"consultants": consultants, "allowed_actions": allowed_actions},
    )
