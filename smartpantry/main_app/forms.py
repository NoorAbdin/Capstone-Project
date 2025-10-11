from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model



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
    

