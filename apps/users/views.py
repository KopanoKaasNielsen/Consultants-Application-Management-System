import csv
import json
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.contrib import messages
from django.contrib.auth import logout, login as auth_login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from django.utils.dateparse import parse_date
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import urlencode

from PyPDF2 import PdfReader, PdfWriter
from weasyprint import HTML

from apps.consultants.emails import send_status_update_email
from apps.consultants.models import Consultant, Notification
from apps.users.constants import (
    CONSULTANTS_GROUP_NAME,
    ADMINS_GROUP_NAME,
    UserRole as Roles,
)
from apps.users.permissions import role_required, user_has_role
from apps.users.audit import log_audit_event
from apps.users.models import AuditLog


IMPERSONATOR_ID_SESSION_KEY = 'impersonator_id'
IMPERSONATOR_USERNAME_SESSION_KEY = 'impersonator_username'
IMPERSONATOR_BACKEND_SESSION_KEY = 'impersonator_backend'

DOCUMENT_FIELD_LABELS = [
    ("photo", "Profile photo"),
    ("id_document", "ID document"),
    ("cv", "Curriculum vitae"),
    ("police_clearance", "Police clearance"),
    ("qualifications", "Qualifications"),
    ("business_certificate", "Business certificate"),
]

DECISION_DOCUMENT_FIELD_LABELS = [
    ("certificate_pdf", "Approval certificate"),
    ("rejection_letter", "Rejection letter"),
]


def _format_file_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None:
        return "Unknown size"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _build_document_entry(file_field, label: str) -> Dict[str, object]:
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

    return {
        "label": label,
        "url": file_field.url,
        "name": file_name,
        "type": extension or "UNKNOWN",
        "size": _format_file_size(size_bytes),
        "file": file_field,
    }


def get_consultant_documents(consultant) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    document_fields: List[Dict[str, object]] = []
    decision_documents: List[Dict[str, object]] = []

    for field_name, label in DOCUMENT_FIELD_LABELS:
        file_field = getattr(consultant, field_name, None)
        if file_field:
            document_fields.append(_build_document_entry(file_field, label))

    for field_name, label in DECISION_DOCUMENT_FIELD_LABELS:
        file_field = getattr(consultant, field_name, None)
        if file_field:
            decision_documents.append(_build_document_entry(file_field, label))

    return document_fields, decision_documents


def _render_consultant_pdf(request, consultant) -> Tuple[bytes, str]:
    document_fields, decision_documents = get_consultant_documents(consultant)
    context = {
        "consultant": consultant,
        "document_fields": document_fields,
        "decision_documents": decision_documents,
        "generated_at": timezone.now(),
    }

    html_string = render_to_string("consultants/application_pdf.html", context)
    pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()

    slug = slugify(consultant.full_name) or "consultant"
    filename = f"{slug}-{consultant.pk}.pdf"

    return pdf_bytes, filename


def _build_pdf_response(request, consultant) -> HttpResponse:
    pdf_bytes, filename = _render_consultant_pdf(request, consultant)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


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


STAFF_DASHBOARD_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]
STAFF_DASHBOARD_STATUS_LABELS = dict(STAFF_DASHBOARD_STATUS_CHOICES)
STAFF_DASHBOARD_SORT_FIELDS = {"created_at", "status"}
STAFF_DASHBOARD_SORT_DIRECTIONS = {"asc", "desc"}


def _normalise_staff_status(value: Optional[str]) -> str:
    if value in STAFF_DASHBOARD_STATUS_LABELS:
        return value
    return "submitted"


def _extract_staff_dashboard_filters(request):
    params = request.POST if request.method == "POST" else request.GET

    active_status = _normalise_staff_status(params.get("status"))
    search_query = params.get("q", "").strip()
    sort_field = params.get("sort", "created_at")
    if sort_field not in STAFF_DASHBOARD_SORT_FIELDS:
        sort_field = "created_at"

    sort_direction = params.get("direction", "desc")
    if sort_direction not in STAFF_DASHBOARD_SORT_DIRECTIONS:
        sort_direction = "desc"

    current_page = params.get("page")

    return active_status, search_query, sort_field, sort_direction, current_page


def _build_staff_dashboard_queryset(active_status, search_query, sort_field, sort_direction):
    consultant_queryset = Consultant.objects.filter(status=active_status).select_related("user")

    if search_query:
        consultant_queryset = consultant_queryset.filter(
            Q(full_name__icontains=search_query)
            | Q(business_name__icontains=search_query)
            | Q(id_number__icontains=search_query)
        )

    consultant_queryset = consultant_queryset.annotate(
        created_at=Coalesce("submitted_at", "updated_at")
    )

    order_prefix = "" if sort_direction == "asc" else "-"

    if sort_field == "status":
        order_by_fields = [f"{order_prefix}status", "-created_at", "-id"]
    else:
        secondary_prefix = "" if sort_direction == "asc" else "-"
        order_by_fields = [f"{order_prefix}created_at", f"{secondary_prefix}id"]

    return consultant_queryset.order_by(*order_by_fields)


def _build_staff_dashboard_results_context(
    *,
    active_status: str,
    search_query: str,
    sort_field: str,
    sort_direction: str,
    paginator,
    page_obj,
    sort_links,
    base_querystring: str,
):
    return {
        "consultants": list(page_obj.object_list),
        "active_status": active_status,
        "active_status_label": STAFF_DASHBOARD_STATUS_LABELS[active_status],
        "paginator": paginator,
        "page_obj": page_obj,
        "consultants_page": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "status_filters": [
            {
                "value": value,
                "label": label,
                "is_active": value == active_status,
            }
            for value, label in STAFF_DASHBOARD_STATUS_CHOICES
        ],
        "search_query": search_query,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "sort_links": sort_links,
        "base_querystring": base_querystring,
    }


@role_required(Roles.STAFF)
def staff_dashboard(request):
    allowed_actions = {
        "approved": "Approve",
        "rejected": "Reject",
        "incomplete": "Request Info",
    }

    (
        active_status,
        search_query,
        sort_field,
        sort_direction,
        current_page,
    ) = _extract_staff_dashboard_filters(request)

    if request.method == "POST":
        consultant_id = request.POST.get("consultant_id")
        action = request.POST.get("action")

        if consultant_id and action in allowed_actions:
            consultant = get_object_or_404(Consultant, id=consultant_id)
            previous_status = consultant.status
            consultant.status = action
            consultant.staff_comment = request.POST.get("comment", "").strip()
            consultant.save(update_fields=["status", "staff_comment"])

            if action == "approved":
                action_type = AuditLog.ActionType.APPROVE_APPLICATION
            elif action == "rejected":
                action_type = AuditLog.ActionType.REJECT_APPLICATION
            else:
                action_type = AuditLog.ActionType.REQUEST_INFO

            audit_log = log_audit_event(
                request.user,
                action_type,
                target_object=f"Consultant:{consultant.pk}",
                metadata={
                    "consultant_id": consultant.pk,
                    "previous_status": previous_status,
                    "new_status": consultant.status,
                },
            )

            notification_type = None
            notification_message = ""

            if action == "approved":
                notification_type = Notification.NotificationType.APPROVED
                notification_message = "Your consultant application has been approved."
            elif action == "rejected":
                notification_type = Notification.NotificationType.REJECTED
                notification_message = "Your consultant application has been rejected."
            elif action == "incomplete":
                notification_type = Notification.NotificationType.COMMENT
                if consultant.staff_comment:
                    notification_message = (
                        "A staff member left a comment on your application: "
                        f"{consultant.staff_comment}"
                    )
                else:
                    notification_message = "A staff member left a comment on your application."

            if notification_type:
                notification_kwargs = {
                    "recipient": consultant.user,
                    "notification_type": notification_type,
                    "message": notification_message,
                }
                if audit_log is not None:
                    notification_kwargs["audit_log"] = audit_log
                Notification.objects.create(**notification_kwargs)

            if action in {"approved", "rejected"}:
                try:
                    send_status_update_email(
                        consultant,
                        action,
                        consultant.staff_comment or "",
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Status updated, but the notification email failed to send.",
                    )

            redirect_params = {"status": active_status, "sort": sort_field, "direction": sort_direction}
            if search_query:
                redirect_params["q"] = search_query
            if current_page:
                redirect_params["page"] = current_page

            query_string = urlencode(redirect_params)
            dashboard_url = f"{reverse('staff_dashboard')}?{query_string}" if query_string else reverse('staff_dashboard')
            return redirect(dashboard_url)

    consultant_queryset = _build_staff_dashboard_queryset(
        active_status,
        search_query,
        sort_field,
        sort_direction,
    )

    paginator = Paginator(consultant_queryset, 10)
    page_number = current_page if request.method == "GET" else None
    page_obj = paginator.get_page(page_number)

    base_query_params = {"status": active_status, "sort": sort_field, "direction": sort_direction}
    if search_query:
        base_query_params["q"] = search_query
    base_querystring = urlencode(base_query_params)

    sort_links = {}
    for field in ("created_at", "status"):
        next_direction = "asc" if sort_field == field and sort_direction == "desc" else "desc"
        params = {"status": active_status, "sort": field, "direction": next_direction}
        if search_query:
            params["q"] = search_query
        sort_links[field] = {
            "querystring": urlencode(params),
            "is_active": sort_field == field,
            "direction": sort_direction if sort_field == field else None,
        }

    recent_applications = (
        Consultant.objects.exclude(submitted_at__isnull=True)
        .select_related("user")
        .order_by("-updated_at", "-id")[:5]
    )

    status_counts = Consultant.objects.aggregate(
        draft=Count("id", filter=Q(status="draft")),
        submitted=Count("id", filter=Q(status="submitted")),
        rejected=Count("id", filter=Q(status="rejected")),
        approved=Count("id", filter=Q(status="approved")),
    )

    consultant_results_context = _build_staff_dashboard_results_context(
        active_status=active_status,
        search_query=search_query,
        sort_field=sort_field,
        sort_direction=sort_direction,
        paginator=paginator,
        page_obj=page_obj,
        sort_links=sort_links,
        base_querystring=base_querystring,
    )

    context = {
        "allowed_actions": allowed_actions,
        "status_counts": status_counts,
        "recent_applications": recent_applications,
        **consultant_results_context,
    }

    if request.headers.get("HX-Request") or request.headers.get("X-Requested-With"):
        return render(request, "staff_dashboard/_consultant_results.html", context)

    return render(request, "staff_dashboard.html", context)


@role_required(Roles.STAFF)
def staff_dashboard_export_csv(request):
    (
        active_status,
        search_query,
        sort_field,
        sort_direction,
        _,
    ) = _extract_staff_dashboard_filters(request)

    consultant_queryset = _build_staff_dashboard_queryset(
        active_status,
        search_query,
        sort_field,
        sort_direction,
    )

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"consultants_{active_status}_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Consultant Name", "Business", "Status", "Submission Date"])

    for consultant in consultant_queryset:
        submitted_at = consultant.submitted_at
        submission_value = submitted_at.isoformat() if submitted_at else ""
        writer.writerow(
            [
                consultant.full_name,
                consultant.business_name,
                consultant.get_status_display(),
                submission_value,
            ]
        )

    log_audit_event(
        request.user,
        AuditLog.ActionType.EXPORT_CSV,
        target_object=f"Consultants:{active_status}",
        metadata={
            "status": active_status,
            "search_query": search_query,
            "sort_field": sort_field,
            "sort_direction": sort_direction,
        },
    )

    return response


@role_required(Roles.STAFF, Roles.BOARD)
def staff_consultant_detail(request, pk: int):
    consultant = get_object_or_404(
        Consultant.objects.select_related("user"),
        pk=pk,
    )

    log_audit_event(
        request.user,
        AuditLog.ActionType.VIEW_CONSULTANT,
        target_object=f"Consultant:{consultant.pk}",
        metadata={
            "consultant_id": consultant.pk,
            "status": consultant.status,
        },
    )

    document_fields, decision_documents = get_consultant_documents(consultant)

    return render(
        request,
        "staff/consultant_detail.html",
        {
            "consultant": consultant,
            "document_fields": document_fields,
            "decision_documents": decision_documents,
        },
    )


@role_required(Roles.STAFF, Roles.BOARD)
def staff_consultant_pdf(request, pk: int):
    consultant = get_object_or_404(Consultant, pk=pk)
    log_audit_event(
        request.user,
        AuditLog.ActionType.EXPORT_PDF,
        target_object=f"Consultant:{consultant.pk}",
        metadata={"consultant_id": consultant.pk},
    )
    return _build_pdf_response(request, consultant)


@role_required(Roles.STAFF)
@require_POST
def staff_consultant_bulk_pdf(request):
    selected_ids = request.POST.getlist("selected_applications")

    if not selected_ids:
        messages.warning(request, "Select at least one application to export.")
        return redirect("officer_applications_list")

    try:
        consultant_ids = sorted({int(value) for value in selected_ids})
    except ValueError:
        messages.error(request, "Invalid selection submitted.")
        return redirect("officer_applications_list")

    consultants = list(
        Consultant.objects.filter(pk__in=consultant_ids).order_by("full_name", "pk")
    )

    if not consultants:
        messages.warning(request, "No matching applications were found for export.")
        return redirect("officer_applications_list")

    pdf_writer = PdfWriter()

    for consultant in consultants:
        pdf_bytes, _ = _render_consultant_pdf(request, consultant)
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            pdf_writer.add_page(page)

    if not pdf_writer.pages:
        messages.warning(request, "The selected applications did not produce any pages to export.")
        return redirect("officer_applications_list")

    output = BytesIO()
    pdf_writer.write(output)
    output.seek(0)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"consultant-applications-{timestamp}.pdf"

    messages.success(
        request,
        "Successfully prepared a combined PDF for the selected applications.",
    )

    response = HttpResponse(output.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    log_audit_event(
        request.user,
        AuditLog.ActionType.EXPORT_BULK_PDF,
        target_object="ConsultantBulk",
        metadata={"consultant_ids": consultant_ids, "filename": filename},
    )
    return response


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    logs = AuditLog.objects.select_related("user")

    action_type = request.GET.get("action_type", "").strip()
    user_filter = request.GET.get("user", "").strip()
    start_date = request.GET.get("start", "").strip()
    end_date = request.GET.get("end", "").strip()
    page_number = request.GET.get("page")

    if action_type:
        logs = logs.filter(action_type=action_type)
    if user_filter:
        logs = logs.filter(user_id=user_filter)

    if start_date:
        parsed_start = parse_date(start_date)
        if parsed_start:
            logs = logs.filter(timestamp__date__gte=parsed_start)
    if end_date:
        parsed_end = parse_date(end_date)
        if parsed_end:
            logs = logs.filter(timestamp__date__lte=parsed_end)

    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(page_number)

    for entry in page_obj.object_list:
        try:
            entry.metadata_pretty = json.dumps(entry.metadata, indent=2, sort_keys=True)
        except TypeError:
            entry.metadata_pretty = str(entry.metadata)

    user_model = get_user_model()
    active_users = user_model.objects.filter(is_active=True).order_by("username")

    filter_params = {
        "action_type": action_type,
        "user": user_filter,
        "start": start_date,
        "end": end_date,
    }

    return render(
        request,
        "admin_dashboard.html",
        {
            "page_obj": page_obj,
            "paginator": paginator,
            "logs": page_obj.object_list,
            "action_choices": AuditLog.ActionType.choices,
            "users": active_users,
            "filters": filter_params,
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
    decision_documents = []

    if application:
        document_fields, decision_documents = get_consultant_documents(application)

    return render(request, 'dashboard.html', {
        'application': application,
        'is_reviewer': False,
        'document_fields': document_fields,
        'decision_documents': decision_documents,
    })


@login_required
def consultant_application_pdf(request):
    if not user_has_role(request.user, Roles.CONSULTANT):
        raise PermissionDenied

    consultant = get_object_or_404(Consultant, user=request.user)
    return _build_pdf_response(request, consultant)
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
