from django.shortcuts import get_object_or_404, redirect, render

from apps.consultants.models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required


@role_required(Roles.STAFF)
def vetting_dashboard(request):
    """Display consultant applications for vetting staff to review."""

    consultants = Consultant.objects.all().order_by("full_name")

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        action = request.POST.get("action")

        if consultant_id and action:
            consultant = get_object_or_404(Consultant, pk=consultant_id)

            status_map = {
                "approve": "approved",
                "reject": "rejected",
                "vet": "vetted",
            }

            new_status = status_map.get(action)
            if new_status:
                consultant.status = new_status
                consultant.save()
                return redirect("vetting_dashboard")

    return render(request, "vetting/dashboard.html", {"consultants": consultants})
