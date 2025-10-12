from django.shortcuts import render, redirect, get_object_or_404
from .forms import CustomUserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import get_user_model
from .models import Item, Recipe, RecipeItem 
from .forms import ItemForm 
from datetime import date , timedelta
from django.contrib import messages 
from django.db.models import Q
import json
from google import genai
from google.genai import types
from django.db import transaction

# Create your views here.


# Initialize the Gemini client (Assumes GEMINI_API_KEY is set in environment)
try:
    client = genai.Client()
except Exception as e:
    # Handle case where API key is not set or client fails to initialize
    print(f"Gemini Client Initialization Error: {e}")
    client = None

# dashboard
User = get_user_model()

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

# --- Recipe Suggestion View (NEW) ---
@login_required
def recipe_suggest(request):
    today = date.today()
    seven_days_from_now = today + timedelta(days=7)

    # Split available items into two lists for prompting
    all_available_items = Item.objects.filter(user=request.user, status='available').order_by('name')
    
    # Items expiring in the next 7 days (prioritized)
    expiring_items = all_available_items.filter(
        expiration_date__gte=today, 
        expiration_date__lte=seven_days_from_now
    ).order_by('expiration_date')
    
    # All other available items (not expiring soon)
    other_items = all_available_items.exclude(
        id__in=expiring_items.values_list('id', flat=True)
    )

    suggested_recipes = []
    error_message = None

    if request.method == 'POST':
        # Get selected item IDs from the form
        selected_item_ids = request.POST.getlist('ingredients')
        
        # Filter items based on user selection
        selected_items = Item.objects.filter(id__in=selected_item_ids)
        
        # Prepare list of selected ingredients for the prompt, flagging expiring items
        expiring_list = [f"{item.name} (EXPIRING SOON, use priority!)" for item in selected_items if item in expiring_items]
        regular_list = [f"{item.name} (regular stock)" for item in selected_items if item not in expiring_items]
        
        ingredient_list = expiring_list + regular_list
        ingredient_prompt_text = ", ".join(ingredient_list)


        if not ingredient_prompt_text:
            error_message = "Please select at least one ingredient to generate recipes."
        elif not client:
            error_message = "Recipe generator is unavailable (API error). Please check API key configuration."
        else:
            # --- STRUCTURED OUTPUT SCHEMA DEFINITION ---
            RecipeIngredientSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "item_name": types.Schema(type=types.Type.STRING, description="The exact name of the ingredient used from the user's pantry."),
                    "amount_required": types.Schema(type=types.Type.INTEGER, description="The integer quantity required for the recipe (e.g., 2, 50, 1)."),
                    "unit": types.Schema(type=types.Type.STRING, description="The unit of measurement (e.g., cups, grams, units, oz).")
                },
                required=["item_name", "amount_required", "unit"]
            )

            SingleRecipeSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="A creative and descriptive title for the recipe."),
                    "description": types.Schema(type=types.Type.STRING, description="A brief summary of the dish and its flavor."),
                    "steps": types.Schema(type=types.Type.STRING, description="The complete, step-by-step cooking instructions, formatted as a single, long, comma-separated string."),
                    "required_ingredients": types.Schema(
                        type=types.Type.ARRAY,
                        items=RecipeIngredientSchema,
                        description="A list of ingredients used from the user's selected items, linking to inventory."
                    ),
                    "full_ingredient_list": types.Schema( # NEW FIELD FOR DISPLAY
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="A comprehensive list of ALL ingredients used in the recipe, including staples like '1/2 cup flour' or '1 tsp salt'."
                    )
                },
                required=["title", "description", "steps", "required_ingredients", "full_ingredient_list"]
            )
            
            # The final expected output is a list of recipes
            RecipeListSchema = types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "recipes": types.Schema(
                        type=types.Type.ARRAY,
                        items=SingleRecipeSchema,
                        description="A list of 3 distinct recipe objects."
                    )
                },
                required=["recipes"]
            )
            # --- END SCHEMA DEFINITION ---

            # System instruction to enforce high-quality, sensible output
            system_instruction = (
                "You are a professional, pragmatic, and creative chef. "
                "Your task is to create 3 distinct, simple, delicious, and achievable recipes using the ingredients provided. "
                "PRIORITIZE using ingredients flagged as 'EXPIRING SOON'. "
                "You must assume the user has common kitchen staples available: Salt, Pepper, Olive Oil, Vegetable Oil, Butter, Flour, Sugar, Eggs, Garlic, and Onion. "
                "Provide a comprehensive 'full_ingredient_list' containing ALL ingredients used (pantry items + staples) for display. "
                "The 'required_ingredients' list must ONLY contain items explicitly selected from the pantry for inventory tracking."
            )
            
            prompt = (
                f"Using ONLY the following selected ingredients from a pantry: {ingredient_prompt_text}. "
                "Generate 3 distinct, sensible recipes. "
                "The steps must be formatted as a single, long, comma-separated string, where each step is separated by a comma."
            )
            
            try:
                # 2. Call the Gemini API with the schema and system instruction
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RecipeListSchema,
                        system_instruction=system_instruction
                    )
                )

                # 3. Parse and Save the Structured Response
                recipe_list_data = json.loads(response.text)
                
                # Process each recipe in the returned list
                for recipe_data in recipe_list_data.get('recipes', []):
                    
                    # Save to Recipe Model
                    new_recipe = Recipe.objects.create(
                        title=recipe_data['title'],
                        description=recipe_data['description'],
                        steps=recipe_data['steps']
                    )

                    # List to store display text for the recipe's ingredients (The old method, now replaced by full_ingredient_list)
                    recipe_ingredients_display = [] 

                    # Save to RecipeItem Model (Link to user's actual Item objects)
                    required_ingredients = recipe_data.get('required_ingredients', [])
                    
                    for req_item in required_ingredients:
                        item_name = req_item.get('item_name', '')
                        amount = req_item.get('amount_required', 1) 
                        unit = req_item.get('unit', 'units') 
                        
                        # Find the actual Item object the user has (case-insensitive match among selected items)
                        try:
                            # Use selected_items, not all_available_items
                            pantry_item = selected_items.get(name__iexact=item_name)
                            
                            RecipeItem.objects.create(
                                recipe=new_recipe,
                                item=pantry_item,
                                amount_required=amount
                            )
                            # Keep this for backward compatibility or debugging, but we use full_ingredient_list now
                            recipe_ingredients_display.append(f"{amount} {unit} of {pantry_item.name}") 
                            
                        except Item.DoesNotExist:
                            pass 

                    # Append the new recipe object and its generated ingredient list
                    suggested_recipes.append({
                        'recipe': new_recipe,
                        'full_ingredients_list': recipe_data.get('full_ingredient_list', []), # PASS THE FULL LIST
                        'ingredients_display': recipe_ingredients_display
                    })
                
            except Exception as e:
                error_message = f"An API or processing error occurred while generating recipes. Please check your inputs. Error: {e}"
                
    context = {
        'title': 'AI Recipe Generator',
        # Pass all available items (expiring prioritized) for display in the form
        'user_items': expiring_items.union(other_items),
        'suggested_recipes': suggested_recipes, # Now a list of dictionaries
        'error_message': error_message,
        'selected_item_ids': selected_item_ids if request.method == 'POST' else [],
        'today': today, # Pass today for the expiration date logic in the template
    }
    return render(request, 'recipe/recipe_suggest.html', context)


# --- NEW VIEW: Consumes items and updates pantry ---
@login_required
@transaction.atomic # Ensures all updates are successful or none are applied
def use_recipe_items(request, recipe_pk):
    """
    Handles item consumption after a recipe is chosen.
    Decrements the quantity of linked Item objects.
    """
    if request.method == 'POST':
        recipe = get_object_or_404(Recipe, pk=recipe_pk)
        
        # 1. Get all items required by this specific recipe (linked via RecipeItem)
        required_items = RecipeItem.objects.filter(recipe=recipe)
        
        # 2. Iterate through and update the user's actual Item objects
        items_consumed_count = 0
        
        for required_item in required_items:
            # The item object is the user's pantry item linked in RecipeItem
            pantry_item = required_item.item
            amount_used = required_item.amount_required
            
            # Check ownership and availability before updating
            if pantry_item.user == request.user and pantry_item.status == 'available':
                
                # Check if we have enough quantity
                if pantry_item.quantity >= amount_used:
                    
                    # Decrement quantity
                    pantry_item.quantity -= amount_used
                    
                    # Check if quantity dropped to zero
                    if pantry_item.quantity == 0:
                        pantry_item.status = 'used'
                        messages.info(request, f"'{pantry_item.name}' completely used up!")
                    
                    pantry_item.save()
                    items_consumed_count += 1
                else:
                    # Log an error or warning if item was selected but quantity is now insufficient
                    messages.warning(request, f"Could not fully consume {pantry_item.name}. Insufficient quantity.")


        if items_consumed_count > 0:
            messages.success(request, f"Pantry updated! Ingredients for '{recipe.title}' have been consumed.")
        else:
            messages.warning(request, "Pantry not updated. No available ingredients were linked to this recipe or quantities were insufficient.")
            
        # Redirect back to the recipe suggestion page or pantry view
        return redirect('my_pantry') 
    
    # If accessed via GET, redirect to avoid direct access
    return redirect('recipe_suggest')

# my-pantry
@login_required
def pantry_view(request):

    context = {
        'title': 'My Pantry Inventory',
    }
    
    return render(request, 'pantry.html', context)

# register
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

