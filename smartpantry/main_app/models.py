from django.db import models
from django.contrib.auth.models import User
# Create your models here.

# Item model
class Item(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    category = models.CharField(max_length=50)
    expiration_date = models.DateField()
    status = models.CharField(max_length=10, 
       choices=[('available', 'Available'),('used','Used')])

    def __str__(self):
     return f"{self.name} ({self.quantity})"
    
# Recipe model
class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    steps = models.TextField()

    def __str__(self):
     return self.title
    

# RecipeItem model
class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    amount_required = models.IntegerField()

    def __str__(self):
     return f"{self.amount_required} of {self.item.name} for {self.recipe.title}"

