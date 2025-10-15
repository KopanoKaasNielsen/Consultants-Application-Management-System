from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.users.constants import ROLE_GROUP_MAP


def _default_groups() -> dict[str, list[str]]:
    """Return the default groups derived from ``ROLE_GROUP_MAP``."""

    group_names = {
        group_name for groups in ROLE_GROUP_MAP.values() for group_name in groups
    }
    return {group_name: [] for group_name in sorted(group_names)}


GROUPS = _default_groups()


class Command(BaseCommand):
    help = 'Create default user groups and assign permissions (if defined)'

    def handle(self, *args, **kwargs):
        for group_name, perms in GROUPS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Group already exists: {group_name}"))

            # Optionally assign permissions
            for perm_codename in perms:
                try:
                    perm = Permission.objects.get(codename=perm_codename)
                    group.permissions.add(perm)
                    self.stdout.write(f"  Added permission: {perm_codename}")
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"  Permission not found: {perm_codename}"))

        self.stdout.write(self.style.SUCCESS("All groups processed."))
