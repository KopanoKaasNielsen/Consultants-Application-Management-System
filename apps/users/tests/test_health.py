import json

from django.urls import reverse

from backend.health import database_health_view, health_view


def test_health_endpoint_returns_ok(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok"}


def test_health_view_returns_simple_status(rf):
    request = rf.get("/health/")
    response = health_view(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


def test_database_health_endpoint_includes_status(client):
    response = client.get(reverse("health-database"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "database" in payload


def test_database_health_view_returns_status(rf):
    request = rf.get("/health/database/")
    response = database_health_view(request)

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["status"] == "ok"
    assert "database" in payload
