"""ASGI routing configuration for websocket connections."""

from __future__ import annotations

from django.urls import path

from apps.users.consumers import StaffNotificationConsumer

websocket_urlpatterns = [
    path("ws/staff/notifications/", StaffNotificationConsumer.as_asgi()),
]
