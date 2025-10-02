import os
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.decisions.views import is_reviewer
from apps.users.constants import (
    ADMINS_GROUP_NAME,
    BACKOFFICE_GROUP_NAME,
    BOARD_COMMITTEE_GROUP_NAME,
    CONSULTANTS_GROUP_NAME,
    COUNTERSTAFF_GROUP_NAME,
    DISAGENTS_GROUP_NAME,
    SENIOR_IMMIGRATION_GROUP_NAME,
    UserRole,
)
from apps.users.permissions import role_required, user_has_role
from backend.settings import base as settings_base
from apps.users.management.commands.seed_test_users import GROUPS as TEST_USER_GROUPS, PASSWORD as TEST_USER_PASSWORD


class RegistrationTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=CONSULTANTS_GROUP_NAME)

    def test_register_assigns_consultant_group(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newconsultant",
                "password1": "complex-password-123",
                "password2": "complex-password-123",
            },
        )

        self.assertRedirects(
            response,
            reverse("login"),
            fetch_redirect_response=False,
        )

        user = get_user_model().objects.get(username="newconsultant")
        self.assertTrue(
            user.groups.filter(name=CONSULTANTS_GROUP_NAME).exists(),
            "Newly registered users should be assigned to the consultants group.",
        )


class SeedUsersCommandTests(TestCase):
    def test_seeded_reviewer_matches_access_control(self):
        """Ensure the seed command populates reviewer groups correctly."""

        call_command("seed_groups")
        call_command("seed_users")

        reviewer = get_user_model().objects.get(username="officer1")
        self.assertTrue(is_reviewer(reviewer))


class SeedTestUsersCommandTests(TestCase):
    @patch("apps.users.management.commands.seed_test_users.get_user_model")
    def test_command_uses_configured_user_model(self, mock_get_user_model):
        created_users = {}

        class DummyUser:
            def __init__(self, username):
                self.username = username
                self.groups = MagicMock()
                self.is_staff = False
                self.is_superuser = False
                self.email = None
                self.password = None

            def set_password(self, password):
                self.password = password

            def save(self):  # pragma: no cover - mock user does not persist
                pass

        def fake_get_or_create(**kwargs):
            username = kwargs["username"]
            user = DummyUser(username)
            created_users[username] = user
            return user, True

        mock_manager = MagicMock()
        mock_manager.get_or_create.side_effect = fake_get_or_create
        mock_user_model = MagicMock()
        mock_user_model.objects = mock_manager
        mock_get_user_model.return_value = mock_user_model

        call_command("seed_test_users")

        mock_get_user_model.assert_called_once_with()
        self.assertEqual(mock_manager.get_or_create.call_count, len(TEST_USER_GROUPS))
        self.assertEqual(set(created_users), set(TEST_USER_GROUPS))

        for username, user in created_users.items():
            self.assertEqual(user.password, TEST_USER_PASSWORD)
            self.assertTrue(user.is_staff)
            if username == "admin1":
                self.assertTrue(user.is_superuser)
            else:
                self.assertFalse(user.is_superuser)
            user.groups.set.assert_called_once()


class LogoutRedirectTests(TestCase):
    def test_logout_redirects_to_login(self):
        """The logout view should redirect to the login page."""

        response = self.client.post(reverse("logout"))
        self.assertRedirects(
            response,
            reverse("login"),
            fetch_redirect_response=False,
        )


class RolePermissionTests(TestCase):
    def setUp(self):
        super().setUp()
        call_command("seed_groups")
        self.user_model = get_user_model()
        self.factory = RequestFactory()

    def _create_user_with_groups(self, username: str, groups):
        user = self.user_model.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="password123",
        )
        group_objs = Group.objects.filter(name__in=groups)
        user.groups.set(group_objs)
        return user

    def test_user_has_role_for_each_mapping(self):
        consultant = self._create_user_with_groups(
            "consultant", [CONSULTANTS_GROUP_NAME]
        )
        staff = self._create_user_with_groups(
            "staffer",
            [
                COUNTERSTAFF_GROUP_NAME,
                BACKOFFICE_GROUP_NAME,
                DISAGENTS_GROUP_NAME,
                SENIOR_IMMIGRATION_GROUP_NAME,
                ADMINS_GROUP_NAME,
            ],
        )
        board = self._create_user_with_groups(
            "board_member", [BOARD_COMMITTEE_GROUP_NAME]
        )

        self.assertTrue(user_has_role(consultant, UserRole.CONSULTANT))
        self.assertTrue(user_has_role(staff, UserRole.STAFF))
        self.assertTrue(user_has_role(board, UserRole.BOARD))

    def test_user_has_role_rejects_unknown_membership(self):
        outsider = self._create_user_with_groups("outsider", [])
        self.assertFalse(user_has_role(outsider, UserRole.STAFF))

    def test_user_has_role_allows_superusers(self):
        superuser = self.user_model.objects.create_superuser(
            username="super", email="super@example.com", password="password123"
        )
        self.assertTrue(user_has_role(superuser, UserRole.BOARD))

    def test_role_required_allows_authorised_user(self):
        staff_user = self._create_user_with_groups(
            "staff_viewer", [BACKOFFICE_GROUP_NAME]
        )

        @role_required(UserRole.STAFF)
        def sample_view(request):
            return HttpResponse("ok")

        request = self.factory.get("/sample")
        request.user = staff_user

        response = sample_view(request)
        self.assertEqual(response.status_code, 200)

    def test_role_required_blocks_unauthorised_user(self):
        consultant = self._create_user_with_groups(
            "consultant_viewer", [CONSULTANTS_GROUP_NAME]
        )

        @role_required(UserRole.BOARD, UserRole.STAFF)
        def sample_view(request):
            return HttpResponse("ok")

        request = self.factory.get("/sample")
        request.user = consultant

        with self.assertRaises(PermissionDenied):
            sample_view(request)


class MonitoringInitTests(SimpleTestCase):
    def test_init_sentry_no_dsn_returns_none(self):
        """Sentry initialisation should be a no-op when no DSN is configured."""

        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            self.assertIsNone(settings_base.init_sentry())
