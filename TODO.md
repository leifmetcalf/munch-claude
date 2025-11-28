# Technical Debt and Future Improvements

## Feature Ideas

### Photo Upload for Munch Log Entries
Allow users to attach a photo when logging a munch. This would capture the meal alongside the visit details.

---

## Technical Debt

### ListCommentForm Missing Author Field
`ListCommentForm` excludes the `author` field and assigns it manually in `restaurantlist_detail` view (line 337). Other forms include all FK fields as hidden inputs. Add `author` to the form's fields with `HiddenInput` widget for consistency.
