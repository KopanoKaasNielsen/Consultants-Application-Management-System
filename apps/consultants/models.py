from django.db import models
from django.contrib.auth import get_user_model

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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    staff_comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.status})"

