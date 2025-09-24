from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import ConsultantForm
from .models import Consultant


@login_required
def submit_application(request):
    """Allow consultants to create or update their application."""
    application = Consultant.objects.filter(user=request.user).first()

    if application and application.status != 'draft':
        messages.info(request, "You have already submitted your application.")
        return redirect('dashboard')

    form = ConsultantForm(request.POST or None, request.FILES or None, instance=application)

    if request.method == 'POST':
        action = request.POST.get('action')

        if form.is_valid():
            consultant = form.save(commit=False)
            consultant.user = request.user
            consultant.status = 'submitted' if action == 'submit' else 'draft'
            consultant.save()

            if action == 'submit':
                messages.success(request, "Application submitted successfully.")
            else:
                messages.info(request, "Draft saved. You can complete it later.")

            return redirect('dashboard')

    return render(
        request,
        'consultants/application_form.html',
        {
            'form': form,
            'is_editing': application is not None and application.status == 'draft',
        },
    )
