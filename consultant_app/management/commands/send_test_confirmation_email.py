"""Queue a test confirmation email task for manual verification."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from consultant_app.tasks import send_confirmation_email


class Command(BaseCommand):
    help = (
        "Enqueue the send_confirmation_email Celery task for a given consultant "
        "identifier or email."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "identifier",
            help="Consultant primary key or email address to use when dispatching the task.",
        )
        parser.add_argument(
            "--queue",
            dest="queue",
            help="Optional Celery queue name (defaults to settings.CELERY_TASK_DEFAULT_QUEUE).",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        identifier = options["identifier"]
        queue = options.get("queue")

        if queue:
            async_result = send_confirmation_email.apply_async((identifier,), queue=queue)
        else:
            async_result = send_confirmation_email.delay(identifier)

        message = (
            "Queued send_confirmation_email for "
            f"'{identifier}' as task {async_result.id}"
        )
        self.stdout.write(self.style.SUCCESS(message))
        return async_result.id
