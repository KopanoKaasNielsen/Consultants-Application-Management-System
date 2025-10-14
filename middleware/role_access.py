"""Middleware enforcing friendly forbidden redirects."""

from __future__ import annotations

from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse


class RoleAccessMiddleware:
    """Redirect ``PermissionDenied`` responses to the shared forbidden page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except PermissionDenied as exc:
            if self._should_skip_redirect(request):
                raise exc
            return self._redirect(request)

        if (
            response.status_code == 403
            and not getattr(response, "rendered_forbidden_page", False)
            and not self._should_skip_redirect(request)
        ):
            return self._redirect(request)

        return response

    @staticmethod
    def _should_skip_redirect(request) -> bool:
        """Return ``True`` when redirecting would break API consumers."""

        path = request.path
        if path.startswith("/api/"):
            return True

        accept = request.headers.get("Accept", "")
        if "application/json" in accept:
            return True

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return True

        return False

    def _redirect(self, request):
        forbidden_url = reverse("forbidden")
        params = {}

        full_path = request.get_full_path()
        if full_path and full_path != forbidden_url:
            params["next"] = full_path

        redirect_target = forbidden_url
        if params:
            redirect_target = f"{forbidden_url}?{urlencode(params)}"

        return HttpResponseRedirect(redirect_target)
