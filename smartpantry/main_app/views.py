from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import get_user_model

# Create your views here.
#home ,about and dashboard
def home(request):
    return render(request, 'home.html')

User = get_user_model()

@login_required
def dashboard(request):
   
    context = {
        'title': 'My Dashboard',
    }
    return render(request, 'user_dashboard.html', context)


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'register.html', context)

