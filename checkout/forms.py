from django import forms
from .models import Order


# Taken from CI Ecommerce project - edited
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('full_name', 'email', 'phone_number',
                  'street_address1', 'street_address2', 'town_or_city',
                  'county', 'country', 'postcode')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'phone_number': 'Phone Number',
            'postcode': 'Postal Code',
            'town_or_city': 'Town or City',
            'street_address1': 'Street Address 1',
            'street_address2': 'Street Address 2',
            'county': 'County',
        }
        self.fields['country'].label = False
        for field in self.fields:
            if field != "country":
                if field == 'full_name':
                    self.fields[field].widget.attrs['autofocus'] = True
                if self.fields[field].required:
                    placeholder = f'{placeholders[field]} *'
                else:
                    placeholder = placeholders[field]
                self.fields[field].widget.attrs['placeholder'] = placeholder
                self.fields[field].label = False
                self.fields[field].widget.attrs['class'] = 'form-control input'
            else:
                self.fields[field].widget.attrs['class'] = 'custom-select'
                self.fields[field].widget.attrs['placeholder'] = False

