from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')

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
    rejection_letter = models.FileField(upload_to='documents/rejection_letters/', blank=True, null=True)
    rejection_letter_generated_at = models.DateTimeField(blank=True, null=True)

    # Status and metadata
    submitted_at = models.DateTimeField(blank=True, null=True)
    is_seen_by_staff = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    staff_comment = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.status})"


class Notification(models.Model):
    """A message delivered to consultants about important application updates."""

    class NotificationType(models.TextChoices):
        APPROVED = "approved", "Application approved"
        REJECTED = "rejected", "Application rejected"
        COMMENT = "comment", "New staff comment"

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)
    audit_log = models.ForeignKey(
        "users.AuditLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):  # pragma: no cover - human readable representation
        return f"Notification to {self.recipient} - {self.notification_type}"

