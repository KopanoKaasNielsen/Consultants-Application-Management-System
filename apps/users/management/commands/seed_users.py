from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

class Command(BaseCommand):
    help = 'Seed initial users for testing'

    def handle(self, *args, **options):
        users = [
            ('consultant1', 'Testpass123!', ['Consultants']),
            ('officer1', 'Testpass123!', ['Immigration Officers']),
            ('dis1', 'Testpass123!', ['DIS']),
            ('board1', 'Testpass123!', ['Board']),
            ('admin1', 'Testpass123!', ['Admins']),
        ]

        for username, password, group_names in users:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password=password)
                for group_name in group_names:
                    group, _ = Group.objects.get_or_create(name=group_name)
                    user.groups.add(group)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Created {username}'))
            else:
                self.stdout.write(f'ℹ️ {username} already exists')
