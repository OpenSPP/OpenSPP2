### 19.0.2.1.0

- feat(ui): honor `bypass_registry_admin_only_crud` in an action's context to exempt
  that action's views (including relational dialogs opened from them) from the
  registry admin-only CRUD restriction; exempt form views also disable the
  blur-triggered urgent (beacon) save so partially-filled new records do not raise
  validation errors on tab switch

### 19.0.2.0.0

- Initial migration to OpenSPP2
