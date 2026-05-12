### 19.0.2.0.1

- fix(role): allow assigning groups to a brand-new role in a single save. Clicking **Add a line** in the role form's Groups tab used to trigger inline creation of a blank `res.groups` row, which raised a required-field validation error and aborted the save. The `implied_ids` field's inner list now uses `create="0"` so the button opens an "Add" picker against existing groups, and `res.users.role.create()` extracts `implied_ids` before `super().create()` and writes them to the role's `group_id` afterwards — mirroring the existing `write()` workaround in `base_user_role` for the same `_inherits` cache-clearing bug.

### 19.0.2.0.0

- Initial migration to OpenSPP2
