from datetime import date
import json

import pytest
from django.contrib.auth import get_user_model

from apps.consultants.models import Consultant


@pytest.mark.django_db
def test_duplicate_values_return_validation_errors(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username='existing',
        email='existing@example.com',
        password='password123',
    )

    Consultant.objects.create(
        user=owner,
        full_name='Existing Consultant',
        id_number='ID-123',
        dob=date(1990, 1, 1),
        gender='M',
        nationality='Kenya',
        email='duplicate@example.com',
        phone_number='0700000000',
        business_name='Existing Business',
        registration_number='REG-789',
        status='submitted',
    )

    payload = {
        'email': 'duplicate@example.com',
        'id_number': 'ID-123',
        'registration_number': 'REG-789',
        'nationality': 'Kenya',
    }

    response = client.post(
        '/api/consultants/validate/',
        data=json.dumps(payload),
        content_type='application/json',
    )

    assert response.status_code == 400
    body = response.json()
    assert body['errors']['email'] == 'A consultant with this email already exists.'
    assert body['errors']['id_number'] == 'A consultant with this ID number already exists.'
    assert body['errors']['registration_number'] == (
        'A consultant with this registration number already exists.'
    )
