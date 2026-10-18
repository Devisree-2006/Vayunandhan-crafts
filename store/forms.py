"""
Store-level forms: registration, contact.
"""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email Address')
    first_name = forms.CharField(max_length=50, required=True, label='First Name')
    last_name = forms.CharField(max_length=50, required=False, label='Last Name')
    phone = forms.CharField(
        max_length=20, required=False, label='Phone / WhatsApp',
        widget=forms.TextInput(attrs={'placeholder': '+91 XXXXX XXXXX'})
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
            from .models import CustomerProfile
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={'phone': self.cleaned_data.get('phone', '')}
            )
        return user


class ContactForm(forms.Form):
    name = forms.CharField(max_length=200, label='Your Name')
    email = forms.EmailField(label='Email Address')
    phone = forms.CharField(max_length=20, required=False, label='Phone / WhatsApp')
    subject = forms.CharField(max_length=200, label='Subject')
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), label='Message')

    def clean_name(self):
        v = self.cleaned_data['name'].strip()
        if len(v) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return v

    def clean_message(self):
        v = self.cleaned_data['message'].strip()
        if len(v) < 10:
            raise forms.ValidationError('Message is too short. Please provide more detail.')
        return v
