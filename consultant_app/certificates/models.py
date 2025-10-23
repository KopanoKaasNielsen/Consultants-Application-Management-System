from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class Certificate(models.Model):
    consultant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    certificate_number = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    issued_on = models.DateField(default=timezone.now)
    valid_until = models.DateField()
    remarks = models.TextField(blank=True, null=True)
    quick_issue = models.BooleanField(default=False)

    def __str__(self):
        return f"Certificate {self.certificate_number} - {self.consultant.username}"
