from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.consultants.models import Consultant
from apps.users.constants import COUNTERSTAFF_GROUP_NAME


@login_required
def vetting_dashboard(request):
    """Display consultant applications for vetting staff to review."""

    if not request.user.groups.filter(name=COUNTERSTAFF_GROUP_NAME).exists():
        return HttpResponseForbidden()

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
