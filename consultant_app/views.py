"""API views for consultant validation."""

from __future__ import annotations

import json
from typing import Any, Dict

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .serializers import ConsultantValidationSerializer


def _flatten_errors(errors: Dict[str, Any]) -> Dict[str, str]:
    """Return a flattened mapping of validation errors."""

    flattened: Dict[str, str] = {}
    for field, messages in errors.items():
        if isinstance(messages, (list, tuple)):
            flattened[field] = str(messages[0]) if messages else ""
        else:
            flattened[field] = str(messages)
    return flattened


@require_POST
def validate_consultant(request):
    """Validate consultant fields for uniqueness constraints."""

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"errors": {"non_field_errors": "Invalid JSON payload."}},
            status=400,
        )

    serializer = ConsultantValidationSerializer(payload)

    if serializer.is_valid():
        return JsonResponse({"valid": True})

    errors = _flatten_errors(serializer.errors)
    return JsonResponse({"errors": errors}, status=400)
