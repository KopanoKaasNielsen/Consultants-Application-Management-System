from django.test import TestCase

# Create your tests here.
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from apps.consultants.models import Consultant


class VettingDashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staffuser', password='testpass')
        vetting_group, _ = Group.objects.get_or_create(name='vetting')
        self.user.groups.add(vetting_group)

        self.client = Client()
        self.client.login(username='staffuser', password='testpass')

        self.consultant = Consultant.objects.create(
            user=self.user,
            full_name='Jane Doe',
            id_number='1234567890',
            dob='1990-01-01',
            gender='F',
            nationality='Botswana',
            email='jane@example.com',
            phone_number='+26712345678',
            business_name='JD Consulting',
            registration_number='REG123',
            status='submitted',
        )

    def test_dashboard_view_status_code(self):
        response = self.client.get(reverse('vetting_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jane Doe')

    def test_unauthorized_user_redirect(self):
        self.client.logout()
        other_user = User.objects.create_user(username='unauth', password='unauthpass')
        self.client.login(username='unauth', password='unauthpass')

        response = self.client.get(reverse('vetting_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_can_approve_consultant(self):
        response = self.client.post(
            reverse('vetting_dashboard'),
            data={'consultant_id': self.consultant.id, 'action': 'approve'},
            follow=True
        )
        self.consultant.refresh_from_db()
        self.assertEqual(self.consultant.status, 'approved')

    def test_can_reject_consultant(self):
        response = self.client.post(
            reverse('vetting_dashboard'),
            data={'consultant_id': self.consultant.id, 'action': 'reject'},
            follow=True
        )
        self.consultant.refresh_from_db()
        self.assertEqual(self.consultant.status, 'rejected')
