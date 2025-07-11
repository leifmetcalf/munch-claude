from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import RestaurantList, RestaurantListItem, Restaurant, User


class RestaurantForm(forms.Form):
    osm_type = forms.CharField(widget=forms.HiddenInput())
    osm_id = forms.CharField(widget=forms.HiddenInput())


class RestaurantListForm(forms.ModelForm):
    class Meta:
        model = RestaurantList
        fields = ['name']


class RestaurantListItemForm(forms.ModelForm):
    class Meta:
        model = RestaurantListItem
        fields = ['restaurant', 'restaurant_list']


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User