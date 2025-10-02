from django.db import models
from django.contrib.auth import get_user_model
from apps.consultants.models import Consultant

User = get_user_model()

class ApplicationAction(models.Model):
    ACTION_CHOICES = [
        ('vetted', 'Marked as Vetted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    consultant = models.ForeignKey(Consultant, on_delete=models.CASCADE, related_name='actions')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_actions')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.consultant.full_name} — {self.action} by {self.actor} @ {self.created_at:%Y-%m-%d %H:%M}"
