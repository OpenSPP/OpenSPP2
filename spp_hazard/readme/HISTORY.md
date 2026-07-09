### 19.0.3.0.0

- **BREAKING**: the 1-5 `severity` Selection on `spp.hazard.incident` and `severity_override` on `spp.hazard.incident.area` are removed and replaced by `severity_id` / `severity_override_id` (Many2one to `spp.vocabulary.code` on the CAP severity namespace). Modules that extend these models must migrate: views that reference `<field name="severity">` / `severity_override`, code that reads `record.severity`, records created with `severity="…"`, and any `fields_to_log` entries or domains naming the old fields. Read `severity_numeric` (below) where a numeric scale is needed.
- **BREAKING**: `spp_hazard` now depends on `spp_vocabulary`.
- **BREAKING**: `category_id` and `start_date` are no longer `required` at the model level (they remain required in the incident form view) so alert ingestion can create incidents that lack them.
- feat: severity is now a CAP v1.2 vocabulary code (`severity_id`, `severity_override_id` on incident areas) instead of a hardcoded 1-5 Selection; adds CAP urgency/certainty/message-type/event fields, alert ingestion (`create_incident_from_alert`), and incident `uuid` (re-land from #76).
- feat: `spp.hazard.incident` exposes a stored `severity_numeric` (5=extreme, 4=severe, 3=moderate, 2=minor, 1=unknown, 0=unset) so downstream ordering and threshold logic can consume a numeric scale without resolving CAP vocabulary codes.
- feat: migration backfills legacy 1-5 severity values onto the vocabulary fields when upgrading from 19.0.2.0.x (1→minor, 2→moderate, 3→severe, 4→severe, 5→extreme); existing values are never overwritten and legacy columns are kept.
- fix: demo incident-area records now set `severity_override_id` vocabulary refs (the removed `severity_override` field broke demo installs).

### 19.0.2.0.2

- fix(security): grant `group_hazard_viewer` to spp_user_roles roles (Registry Viewer, Program Manager, Global/Local Registrar) that the OP#951 menu audit identifies as needing read-only Hazard menu access. Other affected roles defined outside this module (program/CR/farm roles) are wired in their own modules.
- fix(views): gate the "Hazard and Emergency" top-level menu (`hazard_main_menu_root`) on `group_hazard_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Global Finance, Global Support, Global Support Manager, Local Support).

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the hazard impacts list on registrant forms, and hide the table when empty (showing a muted info line instead) (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
