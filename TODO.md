# Technical Debt and Future Improvements

## Feature Ideas

### Photo Upload for Munch Log Entries
Allow users to attach a photo when logging a munch. This would capture the meal alongside the visit details.

---

## Technical Debt

### Medium Priority

#### Manual authorization checks repeated 8 times (`views.py:622, 650, 678, 697, 717, 736, 821, 1035`)
Could use `PermissionDenied` exception or class-based views with `UserPassesTestMixin`.

#### Missing model indexes in `models.py`
- `Restaurant.added_by`
- `RestaurantList.owner`
- `RestaurantListItem` ordering fields

### Low Priority

#### Empty admin.py
No models registered for admin interface.

#### All function-based views
The codebase uses FBVs exclusively. Many could benefit from CBVs with mixins for cleaner authorization and CRUD operations.
