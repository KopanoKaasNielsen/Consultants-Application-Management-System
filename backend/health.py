"""Simple health check view for uptime monitoring."""
from __future__ import annotations

from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health_view(request):
    """Return a lightweight service health response."""
    payload = {"status": "ok"}

    connection = connections["default"]
    db_status = "unknown"

    try:
        if connection.connection is not None and connection.is_usable():
            db_status = "ok"
        elif connection.connection is None:
            # Avoid opening new connections to keep the check fast.
            db_status = "unverified"
        else:
            db_status = "unavailable"
    except OperationalError:
        db_status = "unavailable"

    payload["database"] = db_status
    return JsonResponse(payload)
