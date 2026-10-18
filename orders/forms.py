"""
Order forms: checkout delivery details.
"""
import re
from django import forms


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=200, label='Full Name')
    customer_email = forms.EmailField(label='Email Address')
    customer_phone = forms.CharField(max_length=20, label='Mobile / WhatsApp')
    address_line1 = forms.CharField(max_length=255, label='Address Line 1')
    address_line2 = forms.CharField(max_length=255, required=False, label='Address Line 2')
    city = forms.CharField(max_length=100, label='City')
    state = forms.CharField(max_length=100, label='State')
    pincode = forms.CharField(max_length=10, label='PIN Code')
    delivery_instructions = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Delivery Instructions',
    )
    payment_method = forms.ChoiceField(
        choices=[('razorpay', 'Razorpay'), ('upi_manual', 'Manual UPI')],
        label='Payment Method',
    )

    def clean_customer_name(self):
        v = self.cleaned_data['customer_name'].strip()
        if len(v) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return v

    def clean_customer_phone(self):
        v = self.cleaned_data['customer_phone'].strip()
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise forms.ValidationError('Enter a valid 10-digit mobile number.')
        return v

    def clean_pincode(self):
        v = self.cleaned_data['pincode'].strip()
        if not re.fullmatch(r'[1-9][0-9]{5}', v):
            raise forms.ValidationError('Enter a valid 6-digit PIN code.')
        return v

    def clean_city(self):
        v = self.cleaned_data['city'].strip()
        if len(v) < 2:
            raise forms.ValidationError('Please enter your city.')
        return v

    def clean_state(self):
        v = self.cleaned_data['state'].strip()
        if len(v) < 2:
            raise forms.ValidationError('Please enter your state.')
        return v
