from django.urls import path
from . import views # Import views to connect routes to view functions
from django.contrib.auth import views as auth_views

urlpatterns = [
   # Home
   path('', views.home, name='home'),

   # Authentication
   path('register/', views.register, name='register'),
   path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
   path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),

]