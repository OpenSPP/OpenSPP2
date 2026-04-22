### 19.0.2.0.1

- fix: use @api.model_create_multi for audit_create to support Odoo 19 create overrides (#138)
- fix: Markup sanitization in audit_write and audit_unlink now handles all records, not just the first
- refactor: use `isinstance(value, Markup)` instead of fragile `str(type(...))` comparison in all audit decorator methods
- fix: add HTML escaping to computed `data_html` and `parent_data_html` fields to prevent stored XSS (#50)

### 19.0.2.0.0

- Initial migration to OpenSPP2
