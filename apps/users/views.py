from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST

from apps.consultants.models import Consultant
from apps.users.constants import CONSULTANTS_GROUP_NAME, UserRole as Roles

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            consultant_group, _ = Group.objects.get_or_create(
                name=CONSULTANTS_GROUP_NAME
            )
            user.groups.add(consultant_group)
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


@require_POST
def logout_view(request):
    """Log out the current user via an explicit POST request."""

    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user

    roles = getattr(request, "jwt_roles", set())

    if Roles.BOARD in roles:
        return redirect('decisions_dashboard')

    if Roles.STAFF in roles:
        return redirect('vetting_dashboard')

    if Roles.CONSULTANT not in roles:
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
