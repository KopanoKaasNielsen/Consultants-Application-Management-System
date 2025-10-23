from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.certificates.forms import CertificateForm
from apps.certificates.models import CertificateRenewal
from apps.consultants.models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required

from .services.generator import generate_certificate_pdf

RENEWAL_REQUEST_WINDOW_DAYS = 90


def is_data_clack_officer(user):
    return user.groups.filter(name="Data Clack Officer").exists()


@role_required(Roles.CONSULTANT)
def certificates_dashboard(request):
    consultant = Consultant.objects.filter(user=request.user).first()

    if consultant and consultant.certificate_pdf:
        messages.success(
            request,
            "Application approved! You can download your approval certificate below.",
        )

    pending_renewal = None
    renewals = []
    can_request_renewal = False
    renewal_window_opens = None

    if consultant:
        renewals = list(consultant.certificate_renewals.all())
        for renewal in renewals:
            if renewal.status == CertificateRenewal.Status.PENDING:
                pending_renewal = renewal
                break

        if consultant.certificate_pdf:
            today = timezone.localdate()
            expiry = consultant.certificate_expires_at
            if expiry:
                renewal_window_opens = expiry - timedelta(days=RENEWAL_REQUEST_WINDOW_DAYS)
            can_request_renewal = pending_renewal is None and (
                not expiry or expiry <= today + timedelta(days=RENEWAL_REQUEST_WINDOW_DAYS)
            )

    return render(
        request,
        "certificates/dashboard.html",
        {
            "consultant": consultant,
            "renewals": renewals,
            "pending_renewal": pending_renewal,
            "can_request_renewal": can_request_renewal,
            "renewal_window_opens": renewal_window_opens,
            "renewal_window_days": RENEWAL_REQUEST_WINDOW_DAYS,
        },
    )


@role_required(Roles.CONSULTANT)
@require_POST
def request_certificate_renewal(request):
    consultant = Consultant.objects.filter(user=request.user).first()

    if not consultant or not consultant.certificate_pdf:
        messages.error(
            request,
            "You need an active approval certificate before requesting a renewal.",
        )
        return redirect("certificates:certificates_dashboard")

    if consultant.certificate_renewals.filter(
        status=CertificateRenewal.Status.PENDING
    ).exists():
        messages.info(request, "You already have a pending renewal request.")
        return redirect("certificates:certificates_dashboard")

    expiry = consultant.certificate_expires_at
    today = timezone.localdate()
    window_opens = None
    if expiry:
        window_opens = expiry - timedelta(days=RENEWAL_REQUEST_WINDOW_DAYS)

    if expiry and today < window_opens:
        messages.info(
            request,
            "Renewal requests can only be made within the renewal window.",
        )
        return redirect("certificates:certificates_dashboard")

    CertificateRenewal.objects.create(consultant=consultant)
    messages.success(
        request,
        "Renewal request submitted. A reviewer will process it shortly.",
    )
    return redirect("certificates:certificates_dashboard")


@user_passes_test(is_data_clack_officer)
def generate_certificate(request):
    if request.method == "POST":
        form = CertificateForm(request.POST)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.quick_issue = True
            certificate.save()
            return generate_certificate_pdf(certificate)
    else:
        form = CertificateForm()
    return render(request, "certificates/certificate_form.html", {"form": form})
