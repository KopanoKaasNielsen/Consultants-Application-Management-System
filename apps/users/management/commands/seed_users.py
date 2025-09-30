from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.utils import OperationalError

from apps.decisions.views import REVIEWER_GROUPS

PASSWORD = "Testpass123!"

USERS = [
    ("consultant1", PASSWORD, ["Consultants"]),
    ("counter1", PASSWORD, ["CounterStaff"]),
    ("officer1", PASSWORD, ["BackOffice"]),
    ("dis1", PASSWORD, ["DISAgents"]),
    ("board1", PASSWORD, ["BoardCommittee"]),
    ("senior1", PASSWORD, ["SeniorImmigration"]),
    ("admin1", PASSWORD, ["Admins"]),
]


class Command(BaseCommand):
    help = "Seed initial users for testing"

    def handle(self, *args, **options):
        required_group_names = {name for _, _, names in USERS for name in names}

        groups = {}
        missing_groups = []

        for group_name in required_group_names:
            try:
                groups[group_name] = Group.objects.get(name=group_name)
            except OperationalError as exc:
                raise CommandError(
                    "Database tables are missing. Run 'python manage.py migrate' before seeding users."
                ) from exc
            except Group.DoesNotExist:
                missing_groups.append(group_name)

        if missing_groups:
            raise CommandError(
                "Missing groups: {}. Run 'python manage.py seed_groups' first.".format(
                    ", ".join(sorted(missing_groups))
                )
            )

        reviewer_groups = REVIEWER_GROUPS
        user_model = get_user_model()

        for username, password, group_names in USERS:
            if not user_model.objects.filter(username=username).exists():
                user = user_model.objects.create_user(username=username, password=password)

                if reviewer_groups.intersection(group_names):
                    user.is_staff = True

                for group_name in group_names:
                    user.groups.add(groups[group_name])

                user.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Created {username}"))
            else:
                self.stdout.write(f"ℹ️ {username} already exists")
