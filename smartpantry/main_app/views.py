import json
import time 
import random 
from datetime import date, timedelta
import os
from dotenv import load_dotenv

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages 
from django.db import transaction
from django.contrib.auth import get_user_model, login, logout
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
api_key = os.getenv('_api_key_', '').strip()  # ضع هنا اسم مفتاحك الصحيح في .env

# Models & Forms
from .models import Item, Recipe, RecipeItem 
from .forms import CustomUserCreationForm, ItemForm

User = get_user_model()

MAX_RETRIES = 5

# --- HELPER FUNCTION: Exponential Backoff for API Calls ---
def exponential_backoff_call(client, model, contents, config, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return response
        except genai.errors.ResourceExhaustedError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            else:
                raise e
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            else:
                raise e
    raise Exception("Max retries exceeded for API call.")


# ------------------- DASHBOARD -------------------
@login_required
def dashboard(request):
    
    today = date.today()
    seven_days_from_now = today + timedelta(days=7)

    expiring_soon_items = Item.objects.filter(
        user=request.user, 
        status='available',
        expiration_date__gte=today, 
        expiration_date__lte=seven_days_from_now
    ).order_by('expiration_date')[:3] 

    context = {
        'title': 'User Dashboard',
        'today': today,
        'expiring_soon': expiring_soon_items, 
    }
    return render(request, 'user_dashboard.html', context)


@login_required
@transaction.atomic
def cook_and_save_recipe(request, recipe_pk):
    recipe = get_object_or_404(Recipe, pk=recipe_pk)
    user = request.user

    if request.method == 'POST':
        # 1️⃣ استهلاك المكونات
        required_items = RecipeItem.objects.filter(recipe=recipe)
        items_consumed_count = 0

        for req_item in required_items:
            pantry_item = req_item.item
            amount_used = req_item.amount_required

            if pantry_item.user == user and pantry_item.status == 'available':
                if pantry_item.quantity >= amount_used:
                    pantry_item.quantity -= amount_used
                    if pantry_item.quantity == 0:
                        pantry_item.status = 'used'
                        messages.info(request, f"'{pantry_item.name}' completely used up!")
                    pantry_item.save()
                    items_consumed_count += 1
                else:
                    messages.warning(request, f"Could not fully consume {pantry_item.name}. Insufficient quantity.")

        if items_consumed_count > 0:
            messages.success(request, f"Pantry updated! Ingredients for '{recipe.title}' have been consumed.")
        else:
            messages.warning(request, "Pantry not updated. No available ingredients or insufficient quantities.")

        # 2️⃣ حفظ الوصفة للمستخدم
        recipe.saved_by_users.add(user)
        messages.success(request, f"'{recipe.title}' has been saved to your recipes.")

        return redirect('recipes')

    return redirect('recipe_suggest')


# Recipe view
@login_required
def recipe_saved(request):
    user = request.user

    # 1️⃣ هان التغيير الأساسي
    all_recipes = Recipe.objects.filter(saved_by_users=user).prefetch_related('recipeitem_set__item')

    # باقي الكود كما هو لحساب التطابق والفلترة
    user_pantry_items = Item.objects.filter(user=user).values_list('name', flat=True)
    user_pantry_set = set(name.lower() for name in user_pantry_items)

    ingredient_filter = request.GET.get('ingredient')
    filtered_recipes = []
    all_ingredients_in_saved_recipes = set()

    for recipe in all_recipes:
        recipe_items = recipe.recipeitem_set.all()
        required_ingredients = set(r.item.name.lower() for r in recipe_items)

        for name in required_ingredients:
            all_ingredients_in_saved_recipes.add(name.capitalize())

        matched_count = len(required_ingredients.intersection(user_pantry_set))
        total_required = len(required_ingredients)

        recipe.matched_count = matched_count
        recipe.total_required = total_required
        recipe.pantry_match_score = f"{matched_count}/{total_required}"

        if ingredient_filter:
            if ingredient_filter.lower() in required_ingredients:
                filtered_recipes.append(recipe)
        else:
            filtered_recipes.append(recipe)

    sorted_recipes = sorted(
        filtered_recipes,
        key=lambda r: (r.matched_count, r.total_required, r.id),
        reverse=True
    )

    context = {
        'title': 'My Saved Recipes',
        'recipes': sorted_recipes,
        'pantry_ingredient_names': sorted(list(all_ingredients_in_saved_recipes)),
        'current_filter': ingredient_filter or 'all',
    }
    return render(request, 'recipe/recipes.html', context)


# --- NEW VIEW: Recipe Detail ---
@login_required
def recipe_detail(request, recipe_pk):
    """
    Displays the full details of a saved recipe.
    """
    
    # 1. Fetch the recipe object
    recipe = get_object_or_404(Recipe, pk=recipe_pk)
    
    # 2. Check if this recipe is linked to the user's pantry items to ensure authorization
    if not RecipeItem.objects.filter(recipe=recipe, item__user=request.user).exists():
        messages.error(request, "Recipe not found or you are not authorized to view it.")
        return redirect('recipes')

    # 3. Load the full ingredient list (which was saved as a JSON string)
    try:
        # FIX: The field is now guaranteed to exist and contain a JSON string (default '[]')
        full_ingredients = json.loads(recipe.full_ingredients_json)
    except (json.JSONDecodeError, TypeError):
        full_ingredients = ["Error loading ingredients."]

    # 4. Get the required pantry items for the recipe for a status check
    required_pantry_items = RecipeItem.objects.filter(recipe=recipe)

    context = {
        'title': recipe.title,
        'recipe': recipe,
        'full_ingredients': full_ingredients,
        'required_pantry_items': required_pantry_items,
    }
    return render(request, 'recipe/detail.html', context)


# register
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # This line is correct and logs the user in after successful registration.
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    context = {'form': form}
    return render(request, 'register.html', context)

# CRUD for item
# --- R (Read - List Items) ---
@login_required
def pantry_view(request):
    today = date.today()

    items = Item.objects.filter(user=request.user, status='available')

    category_filter = request.GET.get('category')
    if category_filter and category_filter != 'all':
        items = items.filter(category=category_filter)

    search_query = request.GET.get('search')
    if search_query:

        items = items.filter(name__icontains=search_query)

    sort_by = request.GET.get('sort_by', 'expiring')
    
    if sort_by == 'name':
        items = items.order_by('name')
    elif sort_by == 'added':
        items = items.order_by('-date_added')
    else: 
        items = items.order_by('expiration_date')

    context = {
        'title': 'My Pantry Inventory',
        'items': items,
        'today': today,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'pantry.html', context)


# --- C (Create) ---
@login_required
def item_create(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user  # Assign the current user
            item.save()
            return redirect('my_pantry') 
    else:
        form = ItemForm()
        
    context = {'form': form, 'title': 'Add New Item', 'action': 'Add'}
    return render(request, 'item/item_form.html', context)


# --- U (Update) ---
@login_required
def item_update(request, pk):

    item = get_object_or_404(Item, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect('my_pantry')
    else:
        form = ItemForm(instance=item)
        
    context = {'form': form, 'title': f'Edit {item.name}', 'action': 'Update', 'item': item}
    return render(request, 'item/item_form.html', context)


# --- D (Delete) ---

@login_required
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
        
    if request.method == 'POST':
        item_name = item.name 
        item.delete()
        # 🎯 Add the success message here
        messages.success(request, f'"{item_name}" was successfully deleted from your pantry.')
        return redirect('my_pantry')
        
    return redirect('my_pantry')

@login_required
def item_delete_confirm(request, pk):
    """
    Renders the confirmation page before deletion.
    """
    item = get_object_or_404(Item, pk=pk, user=request.user)
    
    context = {
        'title': 'Confirm Deletion',
        'item': item,
    }
    return render(request, 'item/item_delete_confirm.html', context)


# ------------------- RECIPE SUGGEST -------------------
@login_required
def recipe_suggest(request):
   
    load_dotenv()
    api_key = os.getenv('_api_key_', '').strip()  # Make sure your .env has _api_key_

    today = date.today()
    seven_days_from_now = today + timedelta(days=7)

    error_message = None
    gemini_client = None

    if not api_key:
        error_message = "Recipe generator unavailable: API key missing."
    else:
        try:
            gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            error_message = f"API initialization error: {e}"

    # Pantry items
    all_available_items = Item.objects.filter(user=request.user, status='available').order_by('name')
    expiring_items = all_available_items.filter(expiration_date__lte=seven_days_from_now)
    other_items = all_available_items.exclude(id__in=expiring_items.values_list('id', flat=True))

    suggested_recipes = []
    selected_item_ids = []

    if request.method == 'POST':
        selected_item_ids = request.POST.getlist('ingredients')
        selected_items = Item.objects.filter(id__in=selected_item_ids)

        # Create lists for prompting
        expiring_list = [f"{item.name} ({item.quantity} available, EXPIRING SOON)" for item in selected_items if item in expiring_items]
        regular_list = [f"{item.name} ({item.quantity} available)" for item in selected_items if item not in expiring_items]
        ingredient_prompt_text = ", ".join(expiring_list + regular_list)

        if not ingredient_prompt_text:
            error_message = "Please select at least one ingredient to generate recipes."
        elif not gemini_client:
            pass
        else:
            # --- Schema Definitions ---
            RecipeIngredientSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "item_name": types.Schema(type=types.Type.STRING),
                    "amount_required": types.Schema(type=types.Type.INTEGER),
                    "unit": types.Schema(type=types.Type.STRING)
                },
                required=["item_name", "amount_required", "unit"]
            )

            SingleRecipeSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                    "steps": types.Schema(type=types.Type.STRING),
                    "required_ingredients": types.Schema(type=types.Type.ARRAY, items=RecipeIngredientSchema),
                    "full_ingredient_list": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING))
                },
                required=["title", "description", "steps", "required_ingredients", "full_ingredient_list"]
            )

            RecipeListSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "recipes": types.Schema(type=types.Type.ARRAY, items=SingleRecipeSchema)
                },
                required=["recipes"]
            )

            # --- System Instruction ---
            system_instruction = (
                "You are a professional chef. Generate 3 simple, creative recipes using the provided ingredients. "
                "Prioritize items marked as 'EXPIRING SOON'. "
                "You may also include common pantry ingredients if needed. "
                "'required_ingredients' should only include the ingredients explicitly selected by the user. "
                "'full_ingredient_list' should include all ingredients used, including staples or extras."
            )

            prompt = (
                f"Generate 3 distinct recipes using the selected ingredients: {ingredient_prompt_text}. "
                "Include other common ingredients if needed. Steps should be a single comma-separated string. "
                "List the selected ingredients in 'required_ingredients', and all ingredients in 'full_ingredient_list'."
            )

            try:
                response = exponential_backoff_call(
                    client=gemini_client,
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RecipeListSchema,
                        system_instruction=system_instruction
                    )
                )

                recipe_list_data = json.loads(response.text)
                if not recipe_list_data.get('recipes'):
                    error_message = "API returned no recipes. Try different ingredients."

                for recipe_data in recipe_list_data.get('recipes', []):
                    # Save recipe
                    new_recipe = Recipe.objects.create(
                        title=recipe_data['title'],
                        description=recipe_data['description'],
                        steps=recipe_data['steps'],
                        full_ingredients_json=json.dumps(recipe_data.get('full_ingredient_list', []))
                    )

                    # Link only the selected items for tracking
                    for req_item in recipe_data.get('required_ingredients', []):
                        item_name = req_item.get('item_name', '')
                        amount = req_item.get('amount_required', 1)
                        try:
                            pantry_item = selected_items.get(name__iexact=item_name)
                            RecipeItem.objects.create(recipe=new_recipe, item=pantry_item, amount_required=amount)
                        except Item.DoesNotExist:
                            pass

                    suggested_recipes.append({
                        'recipe': new_recipe,
                        'full_ingredients_list': recipe_data.get('full_ingredient_list', [])
                    })

            except Exception as e:
                error_message = f"Error generating recipes: {e}"

    context = {
        'title': 'AI Recipe Generator',
        'user_items': expiring_items.union(other_items),
        'suggested_recipes': suggested_recipes,
        'error_message': error_message,
        'selected_item_ids': selected_item_ids if request.method == 'POST' else [],
        'today': today,
    }
    return render(request, 'recipe/recipe_suggest.html', context)
