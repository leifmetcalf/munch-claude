# Technical Debt and Future Improvements

## Feature Ideas


## Form Error Handling Issues

### Critical

1. **`restaurantlistitem_create` (views.py:458-531)**
   When form validation fails on POST, the view re-renders but doesn't preserve the invalid form with errors. Users see a blank form with no indication of what went wrong.

2. **`munchlogitem_create` (views.py:961-1022)**
   Same issue - if validation fails (bad date, oversized image), the form re-renders without displaying any errors.

3. **`restaurant_image_add` (views.py:610-628)**
   On failed image upload, the form is re-rendered but POST data is lost because a new empty form is created instead of using the invalid form.

### Moderate

4. **`restaurantlist_update` (views.py:721-736)**
   Redirects after error with only a generic "Please correct the errors below" message - specific field errors are lost because the view redirects away instead of re-rendering.

5. **`restaurantlistitem_update` (views.py:1058-1072)**
   Uses direct POST data access (`request.POST.get("notes")`) without form validation - no errors are ever shown.

### Minor

6. **Non-field errors missing from templates**
   No template displays `form.non_field_errors` - model-level validation errors (from `clean()` methods) would be invisible.
