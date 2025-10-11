import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.urls import reverse

from .emails import send_submission_confirmation_email
from .forms import ConsultantForm
from .models import Consultant, Notification
from apps.users.constants import UserRole as Roles
from apps.users.permissions import role_required


AUTO_SAVE_FIELDS = [
    'full_name',
    'id_number',
    'dob',
    'gender',
    'nationality',
    'email',
    'phone_number',
    'business_name',
    'registration_number',
]

REQUIRED_AUTO_SAVE_FIELDS = [
    'full_name',
    'id_number',
    'dob',
    'gender',
    'nationality',
    'email',
    'phone_number',
    'business_name',
]


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

    show_save_draft = application is None or application.status == 'draft'

    return render(request, 'consultants/application_form.html', {
        'form': form,
        'is_editing': application is not None and application.status == 'draft',
        'show_save_draft': show_save_draft,
        'autosave_enabled': request.user.is_authenticated and show_save_draft,
        'last_saved_at': application.updated_at if application else None,
    })


@role_required(Roles.CONSULTANT)
@require_POST
def autosave_consultant_draft(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required.'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid payload.'}, status=400)

    consultant = Consultant.objects.filter(user=request.user).first()
    now = timezone.now()
    errors = {}

    def cleaned_value(key):
        value = payload.get(key, '')
        if isinstance(value, str):
            return value.strip()
        return value

    if not consultant:
        missing_required = [
            field for field in REQUIRED_AUTO_SAVE_FIELDS if not cleaned_value(field)
        ]
        if missing_required:
            return JsonResponse({
                'status': 'skipped',
                'message': 'Provide your personal and contact details to start auto-saving.',
            })

        consultant = Consultant(user=request.user)

        for field in AUTO_SAVE_FIELDS:
            if field == 'dob':
                dob_value = cleaned_value(field)
                parsed_dob = parse_date(dob_value) if dob_value else None
                if not parsed_dob:
                    errors[field] = 'Enter a valid date.'
                    continue
                consultant.dob = parsed_dob
            elif field == 'registration_number':
                optional_value = cleaned_value(field)
                consultant.registration_number = optional_value or None
            else:
                setattr(consultant, field, cleaned_value(field))

        if errors:
            return JsonResponse({'status': 'error', 'errors': errors}, status=400)

        consultant.status = 'draft'
        consultant.save()
        return JsonResponse({'status': 'saved', 'timestamp': now.isoformat()})

    update_fields = set()

    for field in AUTO_SAVE_FIELDS:
        if field not in payload:
            continue

        if field == 'dob':
            dob_value = cleaned_value(field)
            if not dob_value:
                continue
            parsed_dob = parse_date(dob_value)
            if not parsed_dob:
                errors[field] = 'Enter a valid date.'
                continue
            if consultant.dob != parsed_dob:
                consultant.dob = parsed_dob
                update_fields.add('dob')
        elif field == 'registration_number':
            optional_value = cleaned_value(field)
            new_value = optional_value or None
            if consultant.registration_number != new_value:
                consultant.registration_number = new_value
                update_fields.add('registration_number')
        else:
            new_value = cleaned_value(field)
            if not new_value:
                continue
            if getattr(consultant, field) != new_value:
                setattr(consultant, field, new_value)
                update_fields.add(field)

    if errors:
        return JsonResponse({'status': 'error', 'errors': errors}, status=400)

    if not update_fields:
        timestamp = consultant.updated_at.isoformat() if consultant.updated_at else now.isoformat()
        return JsonResponse({'status': 'unchanged', 'timestamp': timestamp})

    if consultant.status != 'draft':
        consultant.status = 'draft'
        update_fields.add('status')

    consultant.updated_at = now
    update_fields.add('updated_at')
    consultant.save(update_fields=list(update_fields))

    return JsonResponse({'status': 'saved', 'timestamp': now.isoformat()})


@login_required
@require_POST
def mark_notification_read(request, notification_id: int):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("dashboard")
    return redirect(next_url)
