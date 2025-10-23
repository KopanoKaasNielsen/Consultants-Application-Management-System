from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from .forms import CertificateForm
from .services.generator import generate_certificate_pdf

def is_data_clack_officer(user):
    return user.groups.filter(name='Data Clack Officer').exists()

@user_passes_test(is_data_clack_officer)
def generate_certificate(request):
    if request.method == 'POST':
        form = CertificateForm(request.POST)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.quick_issue = True
            certificate.save()
            return generate_certificate_pdf(certificate)
    else:
        form = CertificateForm()
    return render(request, 'certificates/certificate_form.html', {'form': form})
