from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.consultants.models import Consultant


@login_required
def certificates_dashboard(request):
    consultant = Consultant.objects.filter(user=request.user).first()

    return render(
        request,
        "certificates/dashboard.html",
        {
            "consultant": consultant,
        },
    )
