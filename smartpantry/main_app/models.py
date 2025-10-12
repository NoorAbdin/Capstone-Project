from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
# Create your models here.

# Item model


User = get_user_model()

class Item(models.Model):
    # Choices for the 'status' field
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('used','Used'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    quantity = models.IntegerField() # Expects an integer
    category = models.CharField(max_length=50)
    expiration_date = models.DateField() # Required field
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES,
        default='available'
    )

    def __str__(self):
      return f"{self.name} ({self.quantity})"
    
# Recipe model
class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    steps = models.TextField()

    full_ingredients_json = models.TextField(
        default='[]',
        help_text="Stores the full list of ingredients as a JSON string for display.",
        null=True
    )

    def __str__(self):
     return self.title
    

# RecipeItem model
class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    amount_required = models.IntegerField()

    def __str__(self):
     return f"{self.amount_required} of {self.item.name} for {self.recipe.title}"

