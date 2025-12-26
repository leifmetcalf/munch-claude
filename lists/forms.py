from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    RestaurantList,
    RestaurantListItem,
    RestaurantImage,
    User,
    ListComment,
    MunchLogItem,
)


class RestaurantForm(forms.Form):
    osm_type = forms.CharField(widget=forms.HiddenInput())
    osm_id = forms.CharField(widget=forms.HiddenInput())


class RestaurantImageForm(forms.ModelForm):
    class Meta:
        model = RestaurantImage
        fields = ["image", "alt_text", "restaurant", "added_by"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "alt_text": forms.TextInput(
                attrs={
                    "placeholder": "Alt text for accessibility...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
            "restaurant": forms.HiddenInput(),
            "added_by": forms.HiddenInput(),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            # Check file size (limit to 5MB)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")

            # Check file type
            if not image.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file")

        return image


class RestaurantListForm(forms.ModelForm):
    class Meta:
        model = RestaurantList
        fields = ["name", "blurb", "owner"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "My Awesome List",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
            "blurb": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Optional description or notes about this list...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
            "owner": forms.HiddenInput(),
        }


class RestaurantListItemForm(forms.ModelForm):
    class Meta:
        model = RestaurantListItem
        fields = ["restaurant", "restaurant_list", "notes"]
        widgets = {
            "restaurant": forms.HiddenInput(),
            "restaurant_list": forms.HiddenInput(),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional notes about this restaurant...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
        }


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User


class MunchLogItemForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
        help_text="Optional photo from your visit",
    )

    class Meta:
        model = MunchLogItem
        fields = ["restaurant", "munch_log", "visited_date", "notes"]
        widgets = {
            "restaurant": forms.HiddenInput(),
            "munch_log": forms.HiddenInput(),
            "visited_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                },
                format="%Y-%m-%d",
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional notes about this restaurant...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")
            if not image.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file")
        return image


class MunchLogItemUpdateForm(forms.ModelForm):
    """Form for updating only visited_date, notes, and image on a MunchLogItem."""

    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
        help_text="Optional photo from your visit",
    )

    class Meta:
        model = MunchLogItem
        fields = ["visited_date", "notes"]
        widgets = {
            "visited_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow text-sm",
                },
                format="%Y-%m-%d",
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add notes about this restaurant...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow text-sm",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")
            if not image.content_type.startswith("image/"):
                raise forms.ValidationError("Please upload a valid image file")
        return image


class ListCommentForm(forms.ModelForm):
    class Meta:
        model = ListComment
        fields = ["content", "restaurant_list", "author"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add a comment about this list...",
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow",
                }
            ),
            "restaurant_list": forms.HiddenInput(),
            "author": forms.HiddenInput(),
        }


class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow"
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow"
                }
            ),
        }


class RestaurantCreateForm(forms.Form):
    """Form for creating a restaurant. Includes hidden fields for restaurant data."""

    # Restaurant data (hidden fields populated by JavaScript)
    name = forms.CharField(widget=forms.HiddenInput())
    latitude = forms.DecimalField(
        widget=forms.HiddenInput(), max_digits=9, decimal_places=6
    )
    longitude = forms.DecimalField(
        widget=forms.HiddenInput(), max_digits=9, decimal_places=6
    )
    addr_housenumber = forms.CharField(widget=forms.HiddenInput(), required=False)
    addr_street = forms.CharField(widget=forms.HiddenInput(), required=False)
    addr_unit = forms.CharField(widget=forms.HiddenInput(), required=False)
    addr_suburb = forms.CharField(widget=forms.HiddenInput(), required=False)
    addr_state = forms.CharField(widget=forms.HiddenInput(), required=False)
    addr_postcode = forms.CharField(widget=forms.HiddenInput(), required=False)
    cuisine = forms.CharField(widget=forms.HiddenInput(), required=False)
    phone = forms.CharField(widget=forms.HiddenInput(), required=False)
    website = forms.CharField(widget=forms.HiddenInput(), required=False)


TEXT_INPUT_CLASS = "w-full px-3 py-2 border border-yakiimo-purple-border rounded-md focus:border-yakiimo-yellow text-sm"
READONLY_INPUT_CLASS = "w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-100 text-gray-600 text-sm"


class OsmTagsVerifyForm(forms.Form):
    """Form for viewing/editing OSM tags before creating a node."""

    # Coordinates (readonly)
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        widget=forms.TextInput(attrs={"class": READONLY_INPUT_CLASS, "readonly": True}),
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        widget=forms.TextInput(attrs={"class": READONLY_INPUT_CLASS, "readonly": True}),
    )

    # OSM tags (editable)
    amenity = forms.CharField(
        label="amenity",
        initial="restaurant",
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    name = forms.CharField(
        label="name",
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_housenumber = forms.CharField(
        label="addr:housenumber",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_street = forms.CharField(
        label="addr:street",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_unit = forms.CharField(
        label="addr:unit",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_suburb = forms.CharField(
        label="addr:suburb",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_state = forms.CharField(
        label="addr:state",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    addr_postcode = forms.CharField(
        label="addr:postcode",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    cuisine = forms.CharField(
        label="cuisine",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
        help_text="Comma-separated values (e.g., italian, pizza)",
    )
    phone = forms.CharField(
        label="phone",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
    website = forms.CharField(
        label="website",
        required=False,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    )
