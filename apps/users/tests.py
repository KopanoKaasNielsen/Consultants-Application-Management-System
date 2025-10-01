from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.decisions.views import is_reviewer


class SeedUsersCommandTests(TestCase):
    def test_seeded_reviewer_matches_access_control(self):
        """Ensure the seed command populates reviewer groups correctly."""

        call_command("seed_groups")
        call_command("seed_users")

        reviewer = get_user_model().objects.get(username="officer1")
        self.assertTrue(is_reviewer(reviewer))


class LogoutRedirectTests(TestCase):
    def test_logout_redirects_to_login(self):
        """The logout view should redirect to the login page."""

        response = self.client.post(reverse("logout"))
        self.assertRedirects(
            response,
            reverse("login"),
            fetch_redirect_response=False,
        )
