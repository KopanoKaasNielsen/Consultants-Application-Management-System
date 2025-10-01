from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.consultants.models import Consultant


@login_required
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
