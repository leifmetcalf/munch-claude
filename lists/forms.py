from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import RestaurantList, RestaurantListItem, Restaurant, RestaurantImage, User, ListComment, MunchLog, MunchLogItem


class RestaurantForm(forms.Form):
    osm_type = forms.CharField(widget=forms.HiddenInput())
    osm_id = forms.CharField(widget=forms.HiddenInput())


class RestaurantImageForm(forms.ModelForm):
    class Meta:
        model = RestaurantImage
        fields = ['image', 'alt_text', 'restaurant', 'added_by']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'alt_text': forms.TextInput(attrs={
                'placeholder': 'Alt text for accessibility...',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
            'restaurant': forms.HiddenInput(),
            'added_by': forms.HiddenInput(),
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
        fields = ['name', 'blurb', 'owner']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'My Awesome List',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
            'blurb': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Optional description or notes about this list...',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
            'owner': forms.HiddenInput(),
        }


class RestaurantListItemForm(forms.ModelForm):
    class Meta:
        model = RestaurantListItem
        fields = ['restaurant', 'restaurant_list', 'notes']
        widgets = {
            'restaurant': forms.HiddenInput(),
            'restaurant_list': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Optional notes about this restaurant...',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
        }


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User


class MunchLogItemForm(forms.ModelForm):
    class Meta:
        model = MunchLogItem
        fields = ['restaurant', 'munch_log', 'notes']
        widgets = {
            'restaurant': forms.HiddenInput(),
            'munch_log': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Optional notes about this restaurant...',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
        }


class ListCommentForm(forms.ModelForm):
    class Meta:
        model = ListComment
        fields = ['content', 'restaurant_list']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Add a comment about this list...',
                'class': 'w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow'
            }),
            'restaurant_list': forms.HiddenInput(),
        }