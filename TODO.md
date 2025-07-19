# Technical Debt and Future Improvements

## Form Pattern Consistency

### Issue
The codebase currently has inconsistent patterns for handling foreign key fields in forms:

- **RestaurantListForm**: Excludes `owner` field, handled manually in view
- **RestaurantImageForm**: Excludes `restaurant` and `added_by` fields, handled manually in view  
- **RestaurantListItemForm**: Includes foreign key fields as hidden inputs (recently updated)

### Recommendation
Refactor existing forms to use the more idiomatic Django pattern of including all model fields (including foreign keys) as hidden inputs where appropriate. This provides:

- Better validation through Django's form system
- More consistent codebase patterns
- Enhanced security through automatic model validation
- Cleaner view logic

### Specific Changes Needed

1. **RestaurantListForm** (`lists/forms.py`):
   ```python
   # Current
   fields = ['name']
   
   # Proposed
   fields = ['name', 'owner']
   widgets = {
       'owner': forms.HiddenInput(),
   }
   ```

2. **RestaurantImageForm** (`lists/forms.py`):
   ```python
   # Current  
   fields = ['image', 'alt_text']
   
   # Proposed
   fields = ['image', 'alt_text', 'restaurant', 'added_by']
   widgets = {
       'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
       'alt_text': forms.TextInput(attrs={'placeholder': 'Alt text for accessibility...'}),
       'restaurant': forms.HiddenInput(),
       'added_by': forms.HiddenInput(),
   }
   ```

3. **Update corresponding views**:
   - `restaurantlist_create`: Initialize form with `initial={'owner': request.user}`
   - `restaurant_image_add`: Initialize form with `initial={'restaurant': restaurant, 'added_by': request.user}`
   - Remove manual field assignment in views, rely on form validation

### Benefits
- Leverages Django's built-in validation system
- Prevents potential security issues from manual field handling
- More maintainable and consistent code
- Easier to extend with additional validation rules

### Priority
Low - Current implementation works correctly, but refactoring would improve code quality and maintainability.