from django.shortcuts import render

# Create your views here.

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ConsultantForm
from .models import Consultant
#####################
@login_required
def submit_application(request):
    try:
        application = Consultant.objects.get(user=request.user)
        if application.status != 'draft':
            return redirect('dashboard')  # Prevent edits if submitted
        form = ConsultantForm(request.POST or None, request.FILES or None, instance=application)
    except Consultant.DoesNotExist:
        application = None
        form = ConsultantForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if form.is_valid():
            consultant = form.save(commit=False)
            consultant.user = request.user
            consultant.status = 'submitted'
            consultant.save()
            return redirect('dashboard')

    return render(request, 'consultants/application_form.html', {
        'form': form,
        'is_editing': application is not None
    })
