### 19.0.2.0.2

- feat: `audit_disable` context key lets trusted machine flows (e.g. cross-instance replication of records already audited at their source) bypass audit logging and its full-record snapshot reads in create/write/unlink
- perf: skip the full-record snapshot `read(load="_classic_write")` when no audit rule matches the method — `audit_create` read unconditionally and `audit_write` did its post-write read even with zero matching rules, evaluating every non-stored compute (with per-record searches) on every create/write of an audited model

### 19.0.2.0.1

- fix: use @api.model_create_multi for audit_create to support Odoo 19 create overrides (#138)
- fix: Markup sanitization in audit_write and audit_unlink now handles all records, not just the first
- refactor: use `isinstance(value, Markup)` instead of fragile `str(type(...))` comparison in all audit decorator methods
- fix: add HTML escaping to computed `data_html` and `parent_data_html` fields to prevent stored XSS (#50)

### 19.0.2.0.0

- Initial migration to OpenSPP2
