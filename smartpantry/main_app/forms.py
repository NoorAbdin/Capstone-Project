from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Item




User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        label='Email',
        max_length=254,
        required=True, 
        widget=forms.EmailInput()
    )

    class Meta(UserCreationForm.Meta):
        # 1. Use the custom User model
        model = User
        fields = ('username', 'email') + UserCreationForm.Meta.fields[2:]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email
    

CATEGORY_CHOICES = [
    ('Produce', 'Produce'),
    ('Dairy', 'Dairy'),
    ('Meat', 'Meat & Seafood'),
    ('Pantry', 'Dry Goods/Pantry'),
    ('Frozen', 'Frozen'),
    ('Other', 'Other'),
]


class ItemForm(forms.ModelForm):
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, initial='Pantry')
    
    expiration_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Expiration Date' 
    )

    class Meta:
        model = Item
        fields = ['name', 'category', 'quantity', 'expiration_date', 'status']
        labels = {
            'name': 'Item Name',
            'quantity': 'Quantity (Units)',
            'status': 'Item Status',
        }


class ConfirmUnsaveForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="Check to confirm you want to remove this recipe"
    )