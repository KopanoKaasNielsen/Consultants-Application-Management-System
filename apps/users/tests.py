import os
from datetime import date
import csv
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.consultants.models import Consultant
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
from apps.users.views import (
    IMPERSONATOR_BACKEND_SESSION_KEY,
    IMPERSONATOR_ID_SESSION_KEY,
    IMPERSONATOR_USERNAME_SESSION_KEY,
)


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

    def test_logout_rejects_get_requests(self):
        """Logging out should require a POST to prevent CSRF-able GETs."""

        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)


class ImpersonationViewTests(TestCase):
    password = "testpass123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.admin_group, _ = Group.objects.get_or_create(name=ADMINS_GROUP_NAME)

        self.admin_user = self.user_model.objects.create_user(
            username="admin",
            password=self.password,
            email="admin@example.com",
        )
        self.admin_user.groups.add(self.admin_group)

        self.target_user = self.user_model.objects.create_user(
            username="target",
            password=self.password,
            email="target@example.com",
        )

    def test_admin_can_impersonate_user(self):
        self.client.login(username="admin", password=self.password)

        response = self.client.post(
            reverse("start_impersonation"),
            {"user_id": self.target_user.pk},
        )

        self.assertRedirects(response, reverse("home"))

        session = self.client.session
        self.assertEqual(int(session.get("_auth_user_id")), self.target_user.pk)
        self.assertEqual(session[IMPERSONATOR_ID_SESSION_KEY], self.admin_user.pk)
        self.assertEqual(
            session[IMPERSONATOR_USERNAME_SESSION_KEY], self.admin_user.username
        )
        self.assertIsNotNone(session[IMPERSONATOR_BACKEND_SESSION_KEY])

    def test_non_admin_cannot_impersonate(self):
        non_admin = self.user_model.objects.create_user(
            username="regular",
            password=self.password,
        )

        self.client.login(username="regular", password=self.password)
        response = self.client.post(
            reverse("start_impersonation"),
            {"user_id": self.target_user.pk},
        )

        self.assertEqual(response.status_code, 403)
        session = self.client.session
        self.assertNotIn(IMPERSONATOR_ID_SESSION_KEY, session)

    def test_prevents_nested_impersonation(self):
        nested_target = self.user_model.objects.create_user(
            username="nested",
            password=self.password,
        )
        nested_target.groups.add(self.admin_group)

        self.client.login(username="admin", password=self.password)
        self.client.post(reverse("start_impersonation"), {"user_id": nested_target.pk})

        response = self.client.post(
            reverse("start_impersonation"),
            {"user_id": self.target_user.pk},
        )

        self.assertEqual(response.status_code, 400)

    def test_stop_impersonation_restores_original_admin(self):
        self.client.login(username="admin", password=self.password)
        self.client.post(reverse("start_impersonation"), {"user_id": self.target_user.pk})

        response = self.client.post(reverse("stop_impersonation"))

        self.assertRedirects(
            response,
            reverse("impersonation_dashboard"),
            fetch_redirect_response=False,
        )

        session = self.client.session
        self.assertNotIn(IMPERSONATOR_ID_SESSION_KEY, session)
        self.assertNotIn(IMPERSONATOR_USERNAME_SESSION_KEY, session)
        self.assertNotIn(IMPERSONATOR_BACKEND_SESSION_KEY, session)
        self.assertEqual(int(session.get("_auth_user_id")), self.admin_user.pk)


class ImpersonationNavigationTests(TestCase):
    password = "testpass123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.admin_group, _ = Group.objects.get_or_create(name=ADMINS_GROUP_NAME)

    def test_admin_sees_impersonation_link(self):
        admin = self.user_model.objects.create_user(
            username="admin-nav",
            password=self.password,
            email="admin-nav@example.com",
        )
        admin.groups.add(self.admin_group)

        self.client.login(username="admin-nav", password=self.password)

        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            f'href="{reverse("impersonation_dashboard")}"',
            msg_prefix="Admin users should see the impersonation navigation link.",
        )

    def test_non_admin_does_not_see_impersonation_link(self):
        user = self.user_model.objects.create_user(
            username="regular-nav",
            password=self.password,
            email="regular-nav@example.com",
        )

        self.client.login(username="regular-nav", password=self.password)

        response = self.client.get(reverse("home"))

        self.assertNotContains(
            response,
            f'href="{reverse("impersonation_dashboard")}"',
            msg_prefix="Non-admin users should not see the impersonation navigation link.",
        )


class StaffConsultantDetailViewTests(TestCase):
    password = "viewpass123"

    @classmethod
    def setUpTestData(cls):
        call_command("seed_groups")
        cls.user_model = get_user_model()

        cls.staff_user = cls.user_model.objects.create_user(
            username="staffviewer",
            password=cls.password,
            email="staff@example.com",
        )
        staff_group = Group.objects.get(name=BACKOFFICE_GROUP_NAME)
        cls.staff_user.groups.add(staff_group)

        cls.regular_user = cls.user_model.objects.create_user(
            username="regularviewer",
            password=cls.password,
            email="regular@example.com",
        )
        consultant_group = Group.objects.get(name=CONSULTANTS_GROUP_NAME)
        cls.regular_user.groups.add(consultant_group)

        consultant_account = cls.user_model.objects.create_user(
            username="applicant1",
            password=cls.password,
            email="applicant1@example.com",
        )

        cls.consultant = Consultant.objects.create(
            user=consultant_account,
            full_name="Jane Doe",
            id_number="123456789",
            dob=date(1990, 1, 1),
            gender="F",
            nationality="Kenyan",
            email="jane@example.com",
            phone_number="+254700000000",
            business_name="Doe Consulting",
            registration_number="REG-001",
            status="submitted",
            staff_comment="Needs review",
        )

    def test_login_required(self):
        url = reverse("staff_consultant_detail", args=[self.consultant.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_staff_can_view_consultant_detail(self):
        self.client.force_login(self.staff_user)
        url = reverse("staff_consultant_detail", args=[self.consultant.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["consultant"], self.consultant)
        self.assertContains(response, self.consultant.full_name)
        self.assertContains(response, self.consultant.business_name)
        self.assertContains(response, f"mailto:{self.consultant.email}")
        self.assertContains(response, self.consultant.phone_number)
        self.assertContains(response, self.consultant.id_number)
        self.assertContains(response, self.consultant.nationality)

    def test_non_staff_user_denied(self):
        self.client.login(username=self.regular_user.username, password=self.password)
        url = reverse("staff_consultant_detail", args=[self.consultant.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_staff_can_download_consultant_pdf(self):
        self.client.force_login(self.staff_user)
        url = reverse("staff_consultant_pdf", args=[self.consultant.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

        expected_slug = slugify(self.consultant.full_name) or "consultant"
        disposition = response["Content-Disposition"]
        self.assertIn(f"{expected_slug}-{self.consultant.pk}.pdf", disposition)


class ConsultantApplicationPdfTests(TestCase):
    password = "strong-password"

    @classmethod
    def setUpTestData(cls):
        call_command("seed_groups")
        cls.user_model = get_user_model()

        cls.consultant_user = cls.user_model.objects.create_user(
            username="consultantpdf",
            password=cls.password,
            email="consultantpdf@example.com",
        )

        consultant_group = Group.objects.get(name=CONSULTANTS_GROUP_NAME)
        cls.consultant_user.groups.add(consultant_group)

        cls.consultant = Consultant.objects.create(
            user=cls.consultant_user,
            full_name="Alex Export",
            id_number="987654321",
            dob=date(1985, 6, 15),
            gender="M",
            nationality="Kenyan",
            email="alex@example.com",
            phone_number="+254711111111",
            business_name="Export Consulting",
            status="submitted",
        )

    def test_consultant_can_download_pdf(self):
        self.client.login(username=self.consultant_user.username, password=self.password)

        response = self.client.get(reverse("consultant_application_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

        expected_slug = slugify(self.consultant.full_name) or "consultant"
        self.assertIn(f"{expected_slug}-{self.consultant.pk}.pdf", response["Content-Disposition"])

    def test_requires_consultant_role(self):
        other_user = self.user_model.objects.create_user(
            username="nonconsultant",
            password=self.password,
            email="other@example.com",
        )

        self.client.login(username=other_user.username, password=self.password)
        response = self.client.get(reverse("consultant_application_pdf"))

        self.assertEqual(response.status_code, 403)

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


class StaffDashboardFilterTests(TestCase):
    password = "staffpass123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.staff_user = self.user_model.objects.create_user(
            username="staff-filter",
            password=self.password,
            email="staff-filter@example.com",
        )
        self.staff_user.groups.add(self.staff_group)
        self.client.login(username=self.staff_user.username, password=self.password)

    def create_consultant(self, status: str, **overrides) -> Consultant:
        counter = Consultant.objects.count()
        applicant = self.user_model.objects.create_user(
            username=f"{status}_applicant_{counter}",
            password="pass123456",
            email=f"{status}{counter}@example.com",
        )
        defaults = {
            "user": applicant,
            "full_name": f"{status.title()} Applicant",
            "id_number": f"{status[:5]}-{counter}",
            "dob": date(1990, 1, 1),
            "gender": "M",
            "nationality": "Testland",
            "email": applicant.email,
            "phone_number": "1234567890",
            "business_name": "Test Business",
            "status": status,
            "submitted_at": timezone.now(),
        }
        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    def test_defaults_to_submitted_status(self):
        submitted = self.create_consultant("submitted")
        self.create_consultant("approved")

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["page_obj"].object_list),
            [submitted],
        )
        self.assertEqual(response.context["active_status"], "submitted")
        self.assertEqual(response.context["active_status_label"], "Submitted")

    def test_filters_by_requested_status(self):
        approved = self.create_consultant("approved")
        self.create_consultant("submitted")

        response = self.client.get(reverse("staff_dashboard"), {"status": "approved"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["page_obj"].object_list),
            [approved],
        )
        self.assertEqual(response.context["active_status"], "approved")

    def test_invalid_status_falls_back_to_default(self):
        submitted = self.create_consultant("submitted")
        self.create_consultant("rejected")

        response = self.client.get(reverse("staff_dashboard"), {"status": "unknown"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["page_obj"].object_list),
            [submitted],
        )
        self.assertEqual(response.context["active_status"], "submitted")

    def test_post_action_preserves_status_in_redirect(self):
        consultant = self.create_consultant("approved")

        response = self.client.post(
            reverse("staff_dashboard"),
            {
                "consultant_id": consultant.pk,
                "action": "rejected",
                "status": "approved",
                "comment": "Updated after review",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('staff_dashboard')}?status=approved&sort=created_at&direction=desc",
            fetch_redirect_response=False,
        )

        consultant.refresh_from_db()
        self.assertEqual(consultant.status, "rejected")

    def test_paginates_consultants(self):
        submitted_consultants = [
            self.create_consultant("submitted") for _ in range(12)
        ]

        response = self.client.get(reverse("staff_dashboard"), {"status": "submitted"})

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 12)
        self.assertEqual(page_obj.paginator.per_page, 10)
        self.assertTrue(page_obj.has_next())
        self.assertEqual(len(page_obj.object_list), 10)
        self.assertListEqual(
            list(page_obj.object_list),
            list(reversed(submitted_consultants))[:10],
        )

    def test_can_access_subsequent_pages(self):
        submitted_consultants = [
            self.create_consultant("submitted") for _ in range(12)
        ]

        response = self.client.get(
            reverse("staff_dashboard"),
            {"status": "submitted", "page": 2},
        )

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(len(page_obj.object_list), 2)
        self.assertListEqual(
            list(page_obj.object_list),
            list(reversed(submitted_consultants))[10:],
        )

    def test_search_combined_with_status_filters_by_name(self):
        matching = self.create_consultant(
            "submitted",
            full_name="Alex Search",
            business_name="Search Labs",
            id_number="SRCH-100",
        )
        self.create_consultant("submitted", full_name="Other Person")
        self.create_consultant(
            "approved",
            full_name="Alex Search",
            business_name="Search Labs",
        )

        response = self.client.get(
            reverse("staff_dashboard"),
            {"status": "submitted", "q": "alex"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [matching])

    def test_search_combined_with_status_filters_by_identifier(self):
        matching = self.create_consultant(
            "approved",
            full_name="Taylor Lookup",
            business_name="Lookup LLC",
            id_number="LOOK-9001",
        )
        self.create_consultant("approved", id_number="OTHER-1")
        self.create_consultant("rejected", id_number="LOOK-9001")

        response = self.client.get(
            reverse("staff_dashboard"),
            {"status": "approved", "q": "9001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [matching])


class StaffDashboardExportTests(TestCase):
    password = "exportpass123"

    def setUp(self):
        super().setUp()
        self.user_model = get_user_model()
        self.staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.staff_user = self.user_model.objects.create_user(
            username="staff-export",
            password=self.password,
            email="staff-export@example.com",
        )
        self.staff_user.groups.add(self.staff_group)
        self.client.login(username=self.staff_user.username, password=self.password)

    def create_consultant(self, status: str, **overrides) -> Consultant:
        counter = Consultant.objects.count()
        applicant = self.user_model.objects.create_user(
            username=f"export_applicant_{status}_{counter}",
            password="pass123456",
            email=f"export-{status}-{counter}@example.com",
        )
        defaults = {
            "user": applicant,
            "full_name": f"{status.title()} Export {counter}",
            "id_number": f"EXP-{status[:4]}-{counter}",
            "dob": date(1990, 1, 1),
            "gender": "M",
            "nationality": "Testland",
            "email": applicant.email,
            "phone_number": "0123456789",
            "business_name": f"Export Business {counter}",
            "status": status,
            "submitted_at": timezone.now(),
        }
        defaults.update(overrides)
        return Consultant.objects.create(**defaults)

    def test_exports_filtered_queryset(self):
        approved_consultant = self.create_consultant(
            "approved",
            full_name="Included Export",
            business_name="Included Biz",
        )
        self.create_consultant("submitted", full_name="Excluded Export")

        response = self.client.get(reverse("staff_dashboard_export"), {"status": "approved"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertGreaterEqual(len(rows), 2)
        header = rows[0]
        self.assertEqual(
            header,
            ["Consultant Name", "Business", "Status", "Submission Date"],
        )
        self.assertIn(
            [
                approved_consultant.full_name,
                approved_consultant.business_name,
                "Approved",
                approved_consultant.submitted_at.isoformat(),
            ],
            rows[1:],
        )
        self.assertNotIn("Excluded Export", response.content.decode())

    def test_applies_search_terms(self):
        matching = self.create_consultant(
            "submitted",
            full_name="Searchable Export",
            business_name="Search Labs",
        )
        self.create_consultant("submitted", full_name="Other Export")

        response = self.client.get(
            reverse("staff_dashboard_export"),
            {"status": "submitted", "q": "searchable"},
        )

        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(response.content.decode().splitlines()))
        self.assertIn(matching.full_name, response.content.decode())
        self.assertNotIn("Other Export", response.content.decode())
        self.assertEqual(rows[1][0], matching.full_name)

    def test_non_staff_user_cannot_export(self):
        other_user = self.user_model.objects.create_user(
            username="non-staff", password="pass123456", email="other@example.com"
        )
        self.client.logout()
        self.client.login(username=other_user.username, password="pass123456")

        response = self.client.get(reverse("staff_dashboard_export"))

        self.assertEqual(response.status_code, 403)


class MonitoringInitTests(SimpleTestCase):
    def test_init_sentry_no_dsn_returns_none(self):
        """Sentry initialisation should be a no-op when no DSN is configured."""

        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            self.assertIsNone(settings_base.init_sentry())
