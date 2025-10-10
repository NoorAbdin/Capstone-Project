from django.contrib import admin
from .models import Item, Recipe, RecipeItem
# Register your models here.
admin.site.register(Item)

admin.site.register(Recipe)

admin.site.register(RecipeItem)
