from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


GROUPS = {
    'Consultants': [],
    'CounterStaff': [],
    'BackOffice': [],
    'DISAgents': [],
    'BoardCommittee': [],
    'SeniorImmigration': [],
    'Admins': [],
}


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
