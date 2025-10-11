"""ASGI configuration for the backend project with websocket support."""

from __future__ import annotations

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

django_application = get_asgi_application()

try:
    from .routing import websocket_urlpatterns
except Exception as exc:  # pragma: no cover - defensive branch
    raise ImproperlyConfigured("Unable to import websocket routing configuration") from exc

application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
