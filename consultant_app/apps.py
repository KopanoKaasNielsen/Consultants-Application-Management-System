from __future__ import annotations

from django.apps import AppConfig


class ConsultantAppConfig(AppConfig):
    name = "consultant_app"
    verbose_name = "Consultant Applications"

    def ready(self) -> None:  # pragma: no cover - import side effects only
        # Import signal handlers so they are registered when Django starts.
        from . import signals  # noqa: F401

        return None
