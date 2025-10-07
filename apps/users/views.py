import mimetypes
from pathlib import Path
from typing import Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, login as auth_login, get_user_model
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from django.db.models import Count, Q
from django.urls import reverse

from apps.consultants.models import Consultant
from apps.users.constants import (
    CONSULTANTS_GROUP_NAME,
    ADMINS_GROUP_NAME,
    UserRole as Roles,
)
from apps.users.permissions import role_required, user_has_role


IMPERSONATOR_ID_SESSION_KEY = 'impersonator_id'
IMPERSONATOR_USERNAME_SESSION_KEY = 'impersonator_username'
IMPERSONATOR_BACKEND_SESSION_KEY = 'impersonator_backend'


def _user_is_admin(user):
    return user.is_superuser or user.groups.filter(name=ADMINS_GROUP_NAME).exists()


def _user_is_board_or_staff(user):
    if not user.is_authenticated:
        return False

    return user.is_superuser or user.groups.filter(
        name__in=['Board', 'Staff']
    ).exists()


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            consultant_group, _ = Group.objects.get_or_create(
                name=CONSULTANTS_GROUP_NAME
            )
            user.groups.add(consultant_group)
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


@require_POST
def logout_view(request):
    """Log out the current user via an explicit POST request."""

    logout(request)
    return redirect('login')


@login_required
def impersonation_dashboard(request):
    if not _user_is_admin(request.user):
        raise PermissionDenied

    query = request.GET.get('q', '').strip()
    user_model = get_user_model()
    users = user_model.objects.all().order_by('username')

    if query:
        users = users.filter(username__icontains=query)

    users = users.exclude(pk=request.user.pk)

    return render(
        request,
        'impersonation_dashboard.html',
        {
            'users': users,
            'query': query,
            'is_impersonating': IMPERSONATOR_ID_SESSION_KEY in request.session,
        },
    )


@login_required
@require_POST
def start_impersonation(request):
    if IMPERSONATOR_ID_SESSION_KEY in request.session:
        return HttpResponseBadRequest('Already impersonating a user.')

    if not _user_is_admin(request.user):
        raise PermissionDenied

    user_id = request.POST.get('user_id')
    if not user_id:
        return HttpResponseBadRequest('User id is required.')

    user_model = get_user_model()
    target_user = get_object_or_404(user_model, pk=user_id)

    if target_user.pk == request.user.pk:
        return HttpResponseBadRequest('Cannot impersonate yourself.')

    original_user = request.user
    backend = request.session.get(BACKEND_SESSION_KEY)

    if backend is None:
        return HttpResponseBadRequest('Authentication backend missing.')

    auth_login(request, target_user, backend=backend)

    request.session[IMPERSONATOR_ID_SESSION_KEY] = original_user.pk
    request.session[IMPERSONATOR_USERNAME_SESSION_KEY] = original_user.get_username()
    request.session[IMPERSONATOR_BACKEND_SESSION_KEY] = backend

    return redirect('home')


@login_required
@require_POST
def stop_impersonation(request):
    impersonator_id = request.session.get(IMPERSONATOR_ID_SESSION_KEY)
    impersonator_backend = request.session.get(IMPERSONATOR_BACKEND_SESSION_KEY)

    if not impersonator_id or not impersonator_backend:
        return HttpResponseBadRequest('Not currently impersonating a user.')

    user_model = get_user_model()
    original_user = get_object_or_404(user_model, pk=impersonator_id)

    auth_login(request, original_user, backend=impersonator_backend)

    for key in (
        IMPERSONATOR_ID_SESSION_KEY,
        IMPERSONATOR_USERNAME_SESSION_KEY,
        IMPERSONATOR_BACKEND_SESSION_KEY,
    ):
        request.session.pop(key, None)

    return redirect('impersonation_dashboard')


@login_required
def board_dashboard(request):
    if not _user_is_board_or_staff(request.user):
        raise PermissionDenied

    consultants = (
        Consultant.objects.filter(status='submitted')
        .select_related('user')
        .order_by('full_name')
    )

    return render(
        request,
        'board_dashboard.html',
        {
            'consultants': consultants,
        },
    )


@role_required(Roles.STAFF)
def staff_dashboard(request):
    allowed_actions = {
        "approved": "Approve",
        "rejected": "Reject",
        "incomplete": "Request Info",
    }

    status_choices = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    status_labels = dict(status_choices)

    def normalise_status(value: Optional[str]) -> str:
        if value in status_labels:
            return value
        return "submitted"

    if request.method == "POST":
        active_status = normalise_status(request.POST.get("status"))
    else:
        active_status = normalise_status(request.GET.get("status"))

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        action = request.POST.get("action")

        if consultant_id and action in allowed_actions:
            consultant = get_object_or_404(Consultant, id=consultant_id)
            consultant.status = action
            consultant.staff_comment = request.POST.get("comment", "").strip()
            consultant.save(update_fields=["status", "staff_comment"])
            dashboard_url = f"{reverse('staff_dashboard')}?status={active_status}"
            return redirect(dashboard_url)

    consultants = (
        Consultant.objects.filter(status=active_status)
        .select_related("user")
        .order_by("full_name")
    )

    recent_applications = (
        Consultant.objects.exclude(submitted_at__isnull=True)
        .select_related("user")
        .order_by("-submitted_at", "-id")[:5]
    )

    status_counts = Consultant.objects.aggregate(
        draft=Count("id", filter=Q(status="draft")),
        submitted=Count("id", filter=Q(status="submitted")),
        rejected=Count("id", filter=Q(status="rejected")),
        approved=Count("id", filter=Q(status="approved")),
    )

    return render(
        request,
        "staff_dashboard.html",
        {
            "consultants": consultants,
            "allowed_actions": allowed_actions,
            "status_counts": status_counts,
            "recent_applications": recent_applications,
            "active_status": active_status,
            "active_status_label": status_labels[active_status],
            "status_filters": [
                {
                    "value": value,
                    "label": label,
                    "is_active": value == active_status,
                }
                for value, label in status_choices
            ],
        },
    )


@role_required(Roles.STAFF, Roles.BOARD)
def staff_consultant_detail(request, pk: int):
    consultant = get_object_or_404(
        Consultant.objects.select_related("user"),
        pk=pk,
    )

    document_field_labels = [
        ("photo", "Profile photo"),
        ("id_document", "ID document"),
        ("cv", "Curriculum vitae"),
        ("police_clearance", "Police clearance"),
        ("qualifications", "Qualifications"),
        ("business_certificate", "Business certificate"),
        ("certificate_pdf", "Certificate"),
        ("rejection_letter", "Rejection letter"),
    ]

    def format_file_size(size_bytes: Optional[int]) -> str:
        if size_bytes is None:
            return "Unknown size"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    document_fields = []
    for field_name, label in document_field_labels:
        file_field = getattr(consultant, field_name)
        if file_field:
            file_name = file_field.name.rsplit("/", 1)[-1]
            extension = Path(file_name).suffix.replace(".", "").upper()
            if not extension:
                mime_type, _ = mimetypes.guess_type(file_name)
                if mime_type:
                    extension = mime_type.split("/")[-1].upper()

            try:
                size_bytes = file_field.size
            except (OSError, ValueError):
                size_bytes = None

            document_fields.append(
                {
                    "label": label,
                    "url": file_field.url,
                    "name": file_name,
                    "type": extension or "UNKNOWN",
                    "size": format_file_size(size_bytes),
                }
            )

    return render(
        request,
        "staff/consultant_detail.html",
        {
            "consultant": consultant,
            "document_fields": document_fields,
        },
    )


@login_required
def dashboard(request):
    user = request.user

    jwt_roles = getattr(request, "jwt_roles", None)
    roles = set(jwt_roles or [])

    def has_role(role: Roles) -> bool:
        if role in roles:
            return True
        return user_has_role(user, role)

    if has_role(Roles.BOARD):
        return redirect('decisions_dashboard')

    if has_role(Roles.STAFF):
        return redirect('vetting_dashboard')

    if not has_role(Roles.CONSULTANT):
        raise PermissionDenied

    application = Consultant.objects.filter(user=user).first()

    document_fields = []
    document_field_labels = [
        ('photo', 'Profile photo'),
        ('id_document', 'ID document'),
        ('cv', 'Curriculum vitae'),
        ('police_clearance', 'Police clearance'),
        ('qualifications', 'Qualifications'),
        ('business_certificate', 'Business certificate'),
    ]

    if application:
        for field_name, label in document_field_labels:
            file_field = getattr(application, field_name)
            if file_field:
                document_fields.append({
                    'name': field_name,
                    'label': label,
                    'file': file_field,
                })

    return render(request, 'dashboard.html', {
        'application': application,
        'is_reviewer': False,
        'document_fields': document_fields,
    })
def home_view(request):
    return render(request, 'home.html')


class RoleBasedLoginView(LoginView):
    """Login view that redirects users to dashboards based on their role."""

    admin_dashboard_url = '/admin-dashboard/'
    staff_dashboard_url = '/staff-dashboard/'
    applicant_dashboard_url = '/applicant-dashboard/'

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        user = self.request.user

        if user.is_superuser:
            return self.admin_dashboard_url

        if user.groups.filter(name='Staff').exists():
            return self.staff_dashboard_url

        if user.groups.filter(name='Applicant').exists():
            return self.applicant_dashboard_url

        return super().get_success_url()
