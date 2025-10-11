"""Management command to trigger the weekly analytics email."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.users.reports import send_weekly_analytics_report


class Command(BaseCommand):
    help = "Send the weekly consultant analytics report via email."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--base-url",
            dest="base_url",
            help="Optional base URL for resolving assets in the generated PDF.",
        )

    def handle(self, *args, **options):
        base_url = options.get("base_url")

        try:
            sent = send_weekly_analytics_report(base_url=base_url)
        except Exception as exc:
            raise CommandError("Failed to send weekly analytics report") from exc

        if sent:
            self.stdout.write(
                self.style.SUCCESS("Weekly consultant analytics report sent.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "No recipients found for weekly consultant analytics report."
                )
            )
