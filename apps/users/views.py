from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, renderfrom django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from apps.consultants.models import Consultant

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


    application = Consultant.objects.filter(user=request.user).first()

    return render(request, 'dashboard.html', {
        'application': application
    })
def home_view(request):
    return render(request, 'home.html')
