from django.shortcuts import render
from apps.consultants.models import Consultant
# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


############################################################


@login_required
def dashboard(request):
    try:
        application = Consultant.objects.get(user=request.user)
    except Consultant.DoesNotExist:
        application = None

    return render(request, 'dashboard.html', {
        'application': application
    })

