"""Websocket consumers for staff-facing notifications."""

from __future__ import annotations

from typing import Any, Dict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.consultants.models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import user_has_role


class StaffNotificationConsumer(AsyncJsonWebsocketConsumer):
    """Deliver live consultant submission events to staff members."""

    group_name = "staff_consultant_notifications"

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not await self._user_is_staff(user):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_json(
            {
                "type": "staff.init",
                "payload": {"unseen_count": await self._unseen_submission_count()},
            }
        )

    async def disconnect(self, code: int) -> None:  # pragma: no cover - Channels API contract
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await super().disconnect(code)

    async def staff_consultant_created(self, event: Dict[str, Any]) -> None:
        await self.send_json({"type": "staff.new_consultant", "payload": event.get("payload", {})})

    @database_sync_to_async
    def _user_is_staff(self, user) -> bool:
        return user_has_role(user, Roles.STAFF)

    @database_sync_to_async
    def _unseen_submission_count(self) -> int:
        return Consultant.objects.filter(is_seen_by_staff=False).count()
