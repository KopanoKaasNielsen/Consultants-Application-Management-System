from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from .emails import send_submission_confirmation_email
from .forms import ConsultantForm
from .models import Consultant
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required


@role_required(Roles.CONSULTANT)
def submit_application(request):
    application = Consultant.objects.filter(user=request.user).first()

    if application and application.status != 'draft':
        messages.info(request, "You have already submitted your application.")
        return redirect('dashboard')

    form = ConsultantForm(request.POST or None, request.FILES or None, instance=application)

    if request.method == 'POST':
        action = request.POST.get('action', 'draft')
        is_submission = action == 'submit'

        if form.is_valid():
            consultant = form.save(commit=False)
            consultant.user = request.user

            if is_submission:
                consultant.status = 'submitted'
                if not consultant.submitted_at:
                    consultant.submitted_at = timezone.now()
            else:
                consultant.status = 'draft'

            consultant.save()

            if is_submission:
                try:
                    send_submission_confirmation_email(consultant)
                except Exception:
                    messages.warning(
                        request,
                        "Application submitted, but confirmation email failed to send."
                    )

            message = (
                "Application submitted successfully."
                if is_submission else
                "Draft saved. You can complete it later."
            )
            message_fn = messages.success if is_submission else messages.info
            message_fn(request, message)

            return redirect('dashboard')

    return render(request, 'consultants/application_form.html', {
        'form': form,
        'is_editing': application is not None and application.status == 'draft',
        'show_save_draft': application is None or application.status == 'draft',
    })
