from unittest.mock import patch

from urllib.parse import urlencode

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.conf import settings
from apps.consultants.models import Consultant
from apps.decisions.models import ApplicationAction
from apps.users.constants import COUNTERSTAFF_GROUP_NAME, BOARD_COMMITTEE_GROUP_NAME


def _forbidden_target(path: str) -> str:
    return f"{reverse('forbidden')}?{urlencode({'next': path})}"


class VettingDashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='staffuser', password='testpass')
        vetting_group, _ = Group.objects.get_or_create(name=COUNTERSTAFF_GROUP_NAME)
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

    def test_seeded_counterstaff_user_has_access(self):
        counter_staff_user = User.objects.create_user(
            username='counterstaff', password='seededpass'
        )
        counter_staff_user.groups.add(Group.objects.get(name=COUNTERSTAFF_GROUP_NAME))

        seeded_client = Client()
        seeded_client.login(username='counterstaff', password='seededpass')

        response = seeded_client.get(reverse('vetting_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_redirect(self):
        self.client.logout()
        other_user = User.objects.create_user(username='unauth', password='unauthpass')
        self.client.login(username='unauth', password='unauthpass')

        url = reverse('vetting_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, _forbidden_target(url))

    def test_board_member_receives_403(self):
        self.client.logout()
        board_user = User.objects.create_user(username='board', password='boardpass')
        board_group, _ = Group.objects.get_or_create(name=BOARD_COMMITTEE_GROUP_NAME)
        board_user.groups.add(board_group)

        self.client.login(username='board', password='boardpass')

        url = reverse('vetting_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, _forbidden_target(url))

    def test_anonymous_user_redirects_to_login(self):
        anonymous_client = Client()

        response = anonymous_client.get(reverse('vetting_dashboard'))

        self.assertEqual(response.status_code, 302)
        login_url = settings.LOGIN_URL
        expected_url = f"{login_url}?next={reverse('vetting_dashboard')}"
        self.assertEqual(response.url, expected_url)

    @patch('apps.decisions.services.transaction.on_commit')
    @patch('apps.decisions.services.generate_rejection_letter_task.delay')
    @patch('apps.decisions.services.generate_approval_certificate_task.delay')
    def test_can_reject_consultant(
        self,
        mock_approval_delay,
        mock_rejection_delay,
        mock_on_commit,
    ):
        mock_on_commit.side_effect = lambda func, using=None: func()

        response = self.client.post(
            reverse('vetting_dashboard'),
            data={'consultant_id': self.consultant.id, 'action': 'rejected'},
            follow=True
        )

        self.consultant.refresh_from_db()
        self.assertEqual(self.consultant.status, 'rejected')
        self.assertRedirects(response, reverse('vetting_dashboard'))

        action = ApplicationAction.objects.get(consultant=self.consultant)
        self.assertEqual(action.action, 'rejected')
        self.assertEqual(action.actor, self.user)

        generated_by = self.user.get_full_name() or self.user.username
        mock_rejection_delay.assert_called_once_with(
            self.consultant.id, generated_by, self.user.pk
        )
        mock_approval_delay.assert_not_called()
        mock_on_commit.assert_called_once()

    @patch('apps.decisions.services.transaction.on_commit')
    @patch('apps.decisions.services.generate_rejection_letter_task.delay')
    @patch('apps.decisions.services.generate_approval_certificate_task.delay')
    def test_can_vet_consultant(
        self,
        mock_approval_delay,
        mock_rejection_delay,
        mock_on_commit,
    ):
        mock_on_commit.side_effect = lambda func, using=None: func()

        response = self.client.post(
            reverse('vetting_dashboard'),
            data={'consultant_id': self.consultant.id, 'action': 'vetted'},
        )

        self.consultant.refresh_from_db()
        self.assertEqual(self.consultant.status, 'vetted')
        self.assertRedirects(response, reverse('vetting_dashboard'))

        action = ApplicationAction.objects.get(consultant=self.consultant)
        self.assertEqual(action.action, 'vetted')
        self.assertEqual(action.actor, self.user)

        mock_rejection_delay.assert_not_called()
        mock_approval_delay.assert_not_called()
        mock_on_commit.assert_called_once()
