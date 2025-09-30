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

    return render(request, 'dashboard.html', {
        'application': application,
        'is_reviewer': reviewer,
    })
def home_view(request):
    return render(request, 'home.html')
