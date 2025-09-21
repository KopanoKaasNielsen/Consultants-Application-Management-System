from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from .forms import ConsultantForm
from .models import Consultant
from django.contrib import messages





############################################
@login_required
def submit_application(request):
    application = Consultant.objects.filter(user=request.user).first()

    if application and application.status != 'draft':
        messages.info(request, "You have already submitted your application.")
        return redirect('dashboard')

    form = ConsultantForm(request.POST or None, request.FILES or None, instance=application)

    if request.method == 'POST':
        action = request.POST.get('action')  # 'draft' or 'submit'

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

    return render(request, 'consultants/application_form.html', {
        'form': form,
        'is_editing': application is not None and application.status == 'draft',
    })
###########################################
@login_required
def submit_application(request):
    # Get existing application if one exists
    application = Consultant.objects.filter(user=request.user).first()

    if application and application.status != 'draft':
        return redirect('dashboard')  # Prevent edits if not draft

    form = ConsultantForm(
        request.POST or None,
        request.FILES or None,
        instance=application
    )

    if request.method == 'POST':
        if form.is_valid():
            consultant = form.save(commit=False)
            consultant.user = request.user
            consultant.status = 'submitted'
            consultant.save()
            return redirect('dashboard')

    return render(request, 'consultants/application_form.html', {
        'form': form,
        'is_editing': application is not None and application.status == 'draft',
    })
