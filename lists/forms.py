from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import RestaurantList, RestaurantListItem, Restaurant, User


class RestaurantForm(forms.Form):
    osm_type = forms.CharField(widget=forms.HiddenInput())
    osm_id = forms.CharField(widget=forms.HiddenInput())


class RestaurantUpdateForm(forms.ModelForm):
    class Meta:
        model = Restaurant
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (limit to 5MB)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")
            
            # Check file type
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError("Please upload a valid image file")
        
        return image


class RestaurantListForm(forms.ModelForm):
    class Meta:
        model = RestaurantList
        fields = ['name']


class RestaurantListItemForm(forms.ModelForm):
    class Meta:
        model = RestaurantListItem
        fields = ['restaurant', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes about this restaurant...'}),
        }


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User