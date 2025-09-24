from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ConsultantForm
from .models import Consultant


@login_required
def submit_application(request):
    """Handle both draft saves and final submissions for a consultant."""
    application = Consultant.objects.filter(user=request.user).first()

    if application and application.status != 'draft':
        messages.info(request, "You have already submitted your application.")
        return redirect('dashboard')

    form = ConsultantForm(request.POST or None, request.FILES or None, instance=application)

    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action', 'draft')
        is_submission = action == 'submit'

        consultant = form.save(commit=False)
        consultant.user = request.user
        consultant.status = 'submitted' if is_submission else 'draft'
        consultant.save()

        message = (
            "Application submitted successfully."
            if is_submission
            else "Draft saved. You can complete it later."
        )
        message_fn = messages.success if is_submission else messages.info
        message_fn(request, message)

        return redirect('dashboard')

    context = {
        'form': form,
        'is_editing': application is not None and application.status == 'draft',
    }
    return render(request, 'consultants/application_form.html', context)
