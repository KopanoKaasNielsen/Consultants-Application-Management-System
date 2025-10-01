from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from apps.consultants.models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import user_has_role

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def dashboard(request):
    user = request.user

    if user_has_role(user, Roles.BOARD):
        return redirect('decisions_dashboard')

    if user_has_role(user, Roles.STAFF):
        return redirect('vetting_dashboard')

    if not user_has_role(user, Roles.CONSULTANT):
        raise PermissionDenied

    application = Consultant.objects.filter(user=user).first()

    document_fields = []
    document_field_labels = [
        ('photo', 'Profile photo'),
        ('id_document', 'ID document'),
        ('cv', 'Curriculum vitae'),
        ('police_clearance', 'Police clearance'),
        ('qualifications', 'Qualifications'),
        ('business_certificate', 'Business certificate'),
    ]

    if application:
        for field_name, label in document_field_labels:
            file_field = getattr(application, field_name)
            if file_field:
                document_fields.append({
                    'name': field_name,
                    'label': label,
                    'file': file_field,
                })

    return render(request, 'dashboard.html', {
        'application': application,
        'is_reviewer': False,
        'document_fields': document_fields,
    })
def home_view(request):
    return render(request, 'home.html')
