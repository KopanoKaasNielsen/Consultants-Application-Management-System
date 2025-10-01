from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

from apps.consultants.models import Consultant
from apps.decisions.views import is_reviewer

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
    reviewer = is_reviewer(request.user)

    if reviewer:
        return redirect('officer_applications_list')

    application = Consultant.objects.filter(user=request.user).first()

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
        'is_reviewer': reviewer,
        'document_fields': document_fields,
    })
def home_view(request):
    return render(request, 'home.html')
