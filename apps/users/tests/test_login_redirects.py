from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.test import TestCase


class RoleBasedLoginViewTests(TestCase):
    def setUp(self):
        self.login_url = reverse('login')
        self.password = 'testpass123'

    def _create_user(self, username='user', **extra_fields):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username=username,
            password=self.password,
            email=f'{username}@example.com',
            **extra_fields,
        )
        return user

    def test_superuser_redirects_to_admin_dashboard(self):
        user = self._create_user('superuser', is_superuser=True, is_staff=True)

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/admin-dashboard/', fetch_redirect_response=False)

    def test_staff_group_redirects_to_staff_dashboard(self):
        staff_group, _ = Group.objects.get_or_create(name='Staff')
        user = self._create_user('staffuser')
        user.groups.add(staff_group)

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/staff-dashboard/', fetch_redirect_response=False)

    def test_applicant_group_redirects_to_applicant_dashboard(self):
        applicant_group, _ = Group.objects.get_or_create(name='Applicant')
        user = self._create_user('applicantuser')
        user.groups.add(applicant_group)

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/applicant-dashboard/', fetch_redirect_response=False)

    def test_next_parameter_takes_priority(self):
        applicant_group, _ = Group.objects.get_or_create(name='Applicant')
        user = self._create_user('priorityuser')
        user.groups.add(applicant_group)

        response = self.client.post(
            f"{self.login_url}?next=/custom-destination/",
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(
            response,
            '/custom-destination/',
            fetch_redirect_response=False,
        )

    def test_staff_group_takes_priority_over_applicant_group(self):
        staff_group, _ = Group.objects.get_or_create(name='Staff')
        applicant_group, _ = Group.objects.get_or_create(name='Applicant')

        user = self._create_user('multiroleuser')
        user.groups.add(applicant_group, staff_group)

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/staff-dashboard/', fetch_redirect_response=False)

    def test_superuser_redirect_has_priority_over_group_memberships(self):
        staff_group, _ = Group.objects.get_or_create(name='Staff')
        user = self._create_user('superspecial', is_superuser=True)
        user.groups.add(staff_group)

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/admin-dashboard/', fetch_redirect_response=False)

    def test_default_redirect_remains_dashboard(self):
        user = self._create_user('defaultuser')

        response = self.client.post(
            self.login_url,
            {'username': user.username, 'password': self.password},
        )

        self.assertRedirects(response, '/dashboard/', fetch_redirect_response=False)
