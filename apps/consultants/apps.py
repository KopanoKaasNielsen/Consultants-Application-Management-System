from django.apps import AppConfig


class ConsultantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "apps.consultants"

    def ready(self):
        # Import signal handlers so they are registered when the app loads.
        try:  # pragma: no cover - import side effect
            import apps.consultants.signals  # noqa: F401
        except Exception:  # pragma: no cover - defensive logging if import fails
            from logging import getLogger

            getLogger(__name__).exception("Unable to import apps.consultants.signals")
