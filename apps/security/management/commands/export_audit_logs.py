"""Export audit logs in a shareable format."""

from __future__ import annotations

import json
from typing import Iterable, List

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import localtime

from apps.security.models import AuditLog


def _display_user(log: AuditLog, include_contact_details: bool) -> str:
    if log.user is None:
        return "anonymous"

    name = (log.user.get_full_name() or "").strip()
    identifier = name or (log.user.username or f"user-{log.user_id}")

    if include_contact_details and log.user.email:
        return f"{identifier} <{log.user.email}>"

    if name:
        return identifier

    # Avoid leaking email addresses when we fall back to username/id labels.
    return identifier if identifier.startswith("user-") else f"{identifier}"


def _serialise_log(
    log: AuditLog,
    include_ip: bool,
    include_contact_details: bool,
) -> dict:
    payload = {
        "timestamp": localtime(log.timestamp).isoformat(),
        "actor": _display_user(log, include_contact_details),
        "role": log.resolved_role or "",
        "action": log.get_action_code_display(),
        "target": log.target or "",
        "endpoint": log.endpoint or "",
        "context": log.context or {},
    }

    if include_ip and log.client_ip:
        payload["client_ip"] = log.client_ip

    return payload


def _markdown_table(rows: Iterable[dict]) -> str:
    headers = [
        "Timestamp",
        "Actor",
        "Role",
        "Action",
        "Target",
        "Endpoint",
        "Context",
    ]
    lines: List[str] = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for row in rows:
        context_json = json.dumps(row.get("context", {}), ensure_ascii=False, sort_keys=True)
        if len(context_json) > 180:
            context_json = context_json[:177] + "..."

        values = [
            row["timestamp"],
            row["actor"],
            row.get("role", ""),
            row.get("action", ""),
            row.get("target", ""),
            row.get("endpoint", ""),
            context_json,
        ]
        escaped = [value.replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(escaped) + " |")

    return "\n".join(lines)


class Command(BaseCommand):
    """Export recent audit logs in JSON or Markdown format.

    The command is intended to help staff quickly package audit events for
    sharing with support channels such as ChatGPT Plus without exposing
    sensitive details like IP addresses or email addresses by default.
    """

    help = "Export recent security audit logs in a shareable format."

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Number of recent audit logs to include (default: 25).",
        )
        parser.add_argument(
            "--format",
            choices=["json", "markdown"],
            default="markdown",
            help="Output format for the export (default: markdown).",
        )
        parser.add_argument(
            "--include-ip",
            action="store_true",
            help="Include client IP addresses in the export.",
        )
        parser.add_argument(
            "--include-contact-details",
            action="store_true",
            help="Include stored email addresses in the actor column.",
        )

    def handle(self, *args, **options):  # type: ignore[override]
        limit = options["limit"]
        if limit <= 0:
            raise CommandError("--limit must be a positive integer")

        queryset = AuditLog.objects.order_by("-timestamp", "-id")[:limit]
        rows = [
            _serialise_log(
                log,
                include_ip=options["include_ip"],
                include_contact_details=options["include_contact_details"],
            )
            for log in queryset
        ]

        if options["format"] == "json":
            output = json.dumps(rows, indent=2, ensure_ascii=False)
        else:
            output = _markdown_table(rows)

        self.stdout.write(output)
