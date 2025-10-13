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

   # item CRUD
     # R (Read - List)
   path('pantry/', views.pantry_view, name='my_pantry'), 
    
    # C (Create)
   path('pantry/add/', views.item_create, name='item_create'), 
    
    # U (Update)
   path('pantry/edit/<int:pk>/', views.item_update, name='item_update'),
    
    # D (Delete)
   path('pantry/delete/confirm/<int:pk>/', views.item_delete_confirm, name='item_delete_confirm'),
   path('pantry/delete/<int:pk>/', views.item_delete, name='item_delete'), 

   # Recipes 
   path('recipes/suggest/', views.recipe_suggest, name='recipe_suggest'),
   path('recipes/<int:recipe_pk>/', views.recipe_detail, name='recipe_detail'),
   path('recipe/', views.recipe_saved, name='recipes'),
   #path('recipe/save/<int:recipe_pk>/', views.recipe_confirm_save, name='recipe_confirm_save'),
 
   # used-items
   #path('recipe/use/<int:recipe_pk>/', views.use_recipe_items, name='use_recipe_items'), 
   path('recipe/cook-save/<int:recipe_pk>/', views.cook_and_save_recipe, name='cook_and_save_recipe'),
]