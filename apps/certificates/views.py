from django.contrib import messages
from django.shortcuts import render

from apps.consultants.models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required


@role_required(Roles.CONSULTANT)
def certificates_dashboard(request):
    consultant = Consultant.objects.filter(user=request.user).first()

    if consultant and consultant.certificate_pdf:
        messages.success(
            request,
            "Application approved! You can download your approval certificate below.",
        )

    return render(
        request,
        "certificates/dashboard.html",
        {
            "consultant": consultant,
        },
    )
