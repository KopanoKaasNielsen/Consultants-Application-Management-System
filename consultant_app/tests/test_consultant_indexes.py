"""Tests covering Consultant indexes and filtering behaviour."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from apps.consultants.models import Consultant


@pytest.fixture
def consultant_factory(db):
    """Return a callable that creates consultants with sensible defaults."""

    user_model = get_user_model()
    counter = itertools.count()

    def factory(**overrides) -> Consultant:
        index = next(counter)
        user = overrides.pop("user", None)
        if user is None:
            user = user_model.objects.create_user(
                username=f"consultant-index-{index}",
                email=f"consultant-index-{index}@example.com",
                password="testpass123",
            )

        now = timezone.now()

        defaults = {
            "user": user,
            "full_name": overrides.pop("full_name", f"Consultant Index {index}"),
            "id_number": overrides.pop("id_number", f"IDX-{index}"),
            "dob": overrides.pop("dob", date(1990, 1, 1)),
            "gender": overrides.pop("gender", "M"),
            "nationality": overrides.pop("nationality", "Kenya"),
            "email": overrides.pop("email", f"consultant-index-{index}@example.com"),
            "phone_number": overrides.pop("phone_number", "0700000000"),
            "business_name": overrides.pop("business_name", f"Business Index {index}"),
            "registration_number": overrides.pop("registration_number", f"REG-IDX-{index}"),
            "status": overrides.pop("status", "submitted"),
            "submitted_at": overrides.pop("submitted_at", now),
        }

        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    return factory


@pytest.mark.django_db
def test_consultant_status_and_submitted_at_are_indexed(consultant_factory):
    """The schema exposes indexes for status and submitted_at fields."""

    consultant_factory()  # Ensure the table exists and migrations have run.

    table_name = Consultant._meta.db_table
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)

    status_index_exists = any(
        info.get("index") and info.get("columns") == ["status"]
        for info in constraints.values()
    )
    submitted_index_exists = any(
        info.get("index") and info.get("columns") == ["submitted_at"]
        for info in constraints.values()
    )

    assert status_index_exists, "Consultant.status should have a dedicated index"
    assert submitted_index_exists, "Consultant.submitted_at should have a dedicated index"


@pytest.mark.django_db
def test_filtering_by_status_and_submitted_at_unchanged(consultant_factory):
    """Filtering consultants by status and submission date still works as expected."""

    now = timezone.now()
    in_window = consultant_factory(
        status="approved",
        submitted_at=now - timedelta(hours=12),
    )
    consultant_factory(status="approved", submitted_at=now - timedelta(days=5))
    consultant_factory(status="submitted", submitted_at=now - timedelta(hours=6))

    queryset = Consultant.objects.filter(
        status="approved",
        submitted_at__gte=now - timedelta(days=1),
    ).order_by("id")

    assert list(queryset) == [in_window]
