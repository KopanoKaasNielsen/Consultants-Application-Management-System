"""Views that handle consultant document management workflows."""

from __future__ import annotations

import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from apps.security.models import AuditLog
from apps.security.utils import log_audit_event
from apps.users.constants import UserRole as Roles
from apps.users.permissions import user_has_role

from ..forms import DocumentUploadForm
from ..models import Consultant, Document

logger = logging.getLogger(__name__)


def _user_can_manage(user, application: Consultant) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_has_role(user, Roles.STAFF):
        return True
    return application.user_id == user.pk


def _user_can_view(user, application: Consultant) -> bool:
    if _user_can_manage(user, application):
        return True
    return user_has_role(user, Roles.BOARD)


def _build_redirect(request: HttpRequest, application: Consultant) -> str:
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return next_url
    if user_has_role(request.user, Roles.STAFF):
        return reverse("staff_consultant_detail", args=[application.pk])
    return reverse("dashboard")


@login_required
@require_POST
def upload_document(request: HttpRequest, application_id: int) -> HttpResponse:
    application = get_object_or_404(
        Consultant.objects.select_related("user"), pk=application_id
    )

    if not _user_can_manage(request.user, application):
        return HttpResponseForbidden()

    form = DocumentUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for error in form.errors.get("file", []):
            messages.error(request, error)
        return redirect(_build_redirect(request, application))

    uploaded_file = form.cleaned_data["file"]
    document = Document(
        application=application,
        uploaded_by=request.user,
        file=uploaded_file,
    )
    document.original_name = uploaded_file.name
    document.save()

    log_audit_event(
        action_code=AuditLog.ActionCode.UPLOAD_DOCUMENT,
        request=request,
        user=request.user,
        target=f"Consultant:{application.pk}",
        context={
            "document_id": str(document.pk),
            "filename": document.original_name,
            "content_type": document.content_type,
            "size": document.size,
        },
    )

    messages.success(request, _("Document uploaded successfully."))
    return redirect(_build_redirect(request, application))


@login_required
@require_POST
def delete_document(request: HttpRequest, document_id) -> HttpResponse:
    document = get_object_or_404(
        Document.objects.select_related("application"), pk=document_id
    )
    application = document.application

    if not _user_can_manage(request.user, application):
        return HttpResponseForbidden()

    document_name = document.original_name
    storage = document.file.storage if document.file else None
    stored_name = document.file.name if document.file else None

    document.delete()
    if storage and stored_name:
        try:
            storage.delete(stored_name)
        except Exception:  # pragma: no cover - storage backend issues
            logger.exception("Failed to remove document %s from storage", stored_name)

    log_audit_event(
        action_code=AuditLog.ActionCode.DELETE_DOCUMENT,
        request=request,
        user=request.user,
        target=f"Consultant:{application.pk}",
        context={"document_id": str(document_id), "filename": document_name},
    )

    messages.success(request, _("Document removed."))
    return redirect(_build_redirect(request, application))


@login_required
def download_document(request: HttpRequest, document_id, *, inline: bool = False) -> HttpResponse:
    document = get_object_or_404(
        Document.objects.select_related("application", "uploaded_by"), pk=document_id
    )

    if not _user_can_view(request.user, document.application):
        return HttpResponseForbidden()

    try:
        file_handle = document.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("Document is no longer available.") from exc

    disposition = "inline" if inline and document.is_previewable else "attachment"
    response = FileResponse(
        file_handle,
        content_type=document.content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = f'{disposition}; filename="{document.original_name}"'
    return response


@login_required
def preview_document(request: HttpRequest, document_id) -> HttpResponse:
    return download_document(request, document_id, inline=True)


__all__ = [
    "upload_document",
    "delete_document",
    "download_document",
    "preview_document",
]
