import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

class Consultant(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("incomplete", "Incomplete"),
        ("vetted", "Vetted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # Link to the User (consultant account)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='applications',
    )

    # Personal Information
    full_name = models.CharField(max_length=255)
    id_number = models.CharField(max_length=50)
    dob = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)

    # Business Info
    business_name = models.CharField(max_length=255)
    consultant_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Optional classification used for analytics reporting.",
    )
    registration_number = models.CharField(max_length=100, blank=True, null=True)

    # Documents
    photo = models.ImageField(upload_to='documents/photos/', blank=True, null=True)
    id_document = models.FileField(upload_to='documents/id_documents/', blank=True, null=True)
    cv = models.FileField(upload_to='documents/cv/', blank=True, null=True)
    police_clearance = models.FileField(upload_to='documents/police_clearance/', blank=True, null=True)
    qualifications = models.FileField(upload_to='documents/qualifications/', blank=True, null=True)
    business_certificate = models.FileField(upload_to='documents/business_certificates/', blank=True, null=True)

    # Decision documents
    certificate_pdf = models.FileField(upload_to='documents/decision_certificates/', blank=True, null=True)
    certificate_generated_at = models.DateTimeField(blank=True, null=True)
    certificate_expires_at = models.DateField(blank=True, null=True)
    certificate_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    rejection_letter = models.FileField(upload_to='documents/rejection_letters/', blank=True, null=True)
    rejection_letter_generated_at = models.DateTimeField(blank=True, null=True)

    # Status and metadata
    submitted_at = models.DateTimeField(blank=True, null=True)
    is_seen_by_staff = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    staff_comment = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user",),
                name="consultants_unique_application_per_user",
            ),
            models.UniqueConstraint(
                fields=("id_number",),
                name="consultants_unique_id_number",
            ),
            models.UniqueConstraint(
                fields=("email", "nationality"),
                name="consultants_unique_email_per_nationality",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.status})"


class Notification(models.Model):
    """A message delivered to consultants about important application updates."""

    class NotificationType(models.TextChoices):
        APPROVED = "approved", "Application approved"
        REJECTED = "rejected", "Application rejected"
        COMMENT = "comment", "New staff comment"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(default=timezone.now, editable=False)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    audit_log = models.ForeignKey(
        "security.AuditLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):  # pragma: no cover - human readable representation
        return f"Notification to {self.recipient} - {self.notification_type}"


class LogEntry(models.Model):
    """Persisted application log record for staff observability."""

    LEVEL_CHOICES = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    logger_name = models.CharField(max_length=255, db_index=True)
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES)
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultant_logs",
    )
    context = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ("-timestamp", "-id")

    def __str__(self) -> str:  # pragma: no cover - human readable representation
        return f"[{self.level}] {self.logger_name}: {self.message[:75]}"

