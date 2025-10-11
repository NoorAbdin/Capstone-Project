from django.urls import path
from . import views # Import views to connect routes to view functions
from django.contrib.auth import views as auth_views



urlpatterns = [
   # Home
   path('', views.home, name='home'),

   # Authentication
   path('register/', views.register, name='register'),

   # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'), 
]