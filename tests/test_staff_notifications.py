import datetime

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

from apps.consultants.models import Consultant
from backend.asgi import application


@pytest.mark.django_db
def test_consultant_creation_broadcasts_staff_event(settings):
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

    channel_layer = get_channel_layer()
    channel_name = async_to_sync(channel_layer.new_channel)("test-channel")
    async_to_sync(channel_layer.group_add)(
        "staff_consultant_notifications", channel_name
    )

    user_model = get_user_model()
    applicant = user_model.objects.create_user("applicant", password="password123")

    consultant = Consultant.objects.create(
        user=applicant,
        full_name="Jane Smith",
        id_number="ID123456",
        dob=datetime.date(1990, 1, 1),
        gender="F",
        nationality="Wonderland",
        email="jane@example.com",
        phone_number="123456789",
        business_name="Wonder Consulting",
    )

    message = async_to_sync(channel_layer.receive)(channel_name)
    assert message["type"] == "staff_consultant_created"

    payload = message["payload"]
    assert payload["consultant"]["id"] == consultant.pk
    assert payload["unseen_count"] == 1
    assert payload["status_counts"]["draft"] >= 1


@pytest.mark.django_db(transaction=True)
def test_staff_consumer_receives_notifications(settings):
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

    user_model = get_user_model()
    staff_user = user_model.objects.create_user("staff", password="password123")
    staff_group, _ = Group.objects.get_or_create(name="Staff")
    staff_user.groups.add(staff_group)

    client = Client()
    client.force_login(staff_user)
    session_key = client.session.session_key

    async def _run_scenario():
        communicator = WebsocketCommunicator(
            application,
            "/ws/staff/notifications/",
            headers=[(b"cookie", f"sessionid={session_key}".encode())],
        )

        connected, _ = await communicator.connect()
        assert connected is True

        init_message = await communicator.receive_json_from()
        assert init_message["type"] == "staff.init"
        assert "unseen_count" in init_message["payload"]

        applicant = await database_sync_to_async(user_model.objects.create_user)(
            "applicant2", password="password123"
        )

        consultant = await database_sync_to_async(Consultant.objects.create)(
            user=applicant,
            full_name="Alex Doe",
            id_number="ID654321",
            dob=datetime.date(1992, 5, 17),
            gender="O",
            nationality="Fictionland",
            email="alex@example.com",
            phone_number="555555555",
            business_name="Alex Ventures",
        )

        event_message = await communicator.receive_json_from()
        assert event_message["type"] == "staff.new_consultant"

        event_payload = event_message["payload"]
        assert event_payload["consultant"]["id"] == consultant.pk
        assert event_payload["consultant"]["full_name"] == "Alex Doe"
        assert event_payload["unseen_count"] >= 1

        await communicator.disconnect()

    async_to_sync(_run_scenario)()
