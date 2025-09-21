from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User

GROUPS = {
    'officer1': 'BackOffice',
    'dis1': 'DISAgents',
    'board1': 'BoardCommittee',
    'senior1': 'SeniorImmigration',
    'admin1': 'Admins',
    'consultant1': 'Consultants',
}

PASSWORD = 'Testpass123!'

class Command(BaseCommand):
    help = "Seed test users with roles for each reviewer group"

    def handle(self, *args, **kwargs):
        for username, groupname in GROUPS.items():
            # Get or create the group
            group, _ = Group.objects.get_or_create(name=groupname)

            # Get or create the user
            user, created = User.objects.get_or_create(username=username)
            user.set_password(PASSWORD)
            user.email = f"{username}@example.com"
            user.is_active = True
            user.is_staff = True

            # Only admin1 is a superuser
            if username == 'admin1':
                user.is_superuser = True
            else:
                user.is_superuser = False

            user.save()
            user.groups.set([group])
            self.stdout.write(self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} user: {username} ({groupname})"
            ))

        self.stdout.write(self.style.SUCCESS("✅ Test users seeded successfully!"))
