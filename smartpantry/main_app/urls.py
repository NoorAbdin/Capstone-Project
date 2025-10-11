from django.urls import path
from . import views # Import views to connect routes to view functions
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views



urlpatterns = [
   # Home and about
   path('', TemplateView.as_view(template_name='home.html'), name='home'),
   path('about/', TemplateView.as_view(template_name='about.html'), name='about'),

   # Authentication
   path('register/', views.register, name='register'),

   # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'), 
]