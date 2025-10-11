from django.shortcuts import render, redirect, get_object_or_404
from .forms import CustomUserCreationForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required 
from django.contrib.auth import get_user_model
from .models import Item 
from .forms import ItemForm 
from datetime import date , timedelta
from django.contrib import messages 
from django.db.models import Q

# Create your views here.
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

