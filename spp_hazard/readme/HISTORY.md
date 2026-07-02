### 19.0.2.1.0

- feat: severity is now a CAP v1.2 vocabulary code (`severity_id`, `severity_override_id` on incident areas) instead of a hardcoded 1-5 Selection; adds CAP urgency/certainty/message-type/event fields, alert ingestion (`create_incident_from_alert`), and incident `uuid` (re-land from #76).
- feat: migration backfills legacy 1-5 severity values onto the vocabulary fields when upgrading from 19.0.2.0.x (1→minor, 2→moderate, 3→severe, 4→severe, 5→extreme); existing values are never overwritten and legacy columns are kept.
- fix: demo incident-area records now set `severity_override_id` vocabulary refs (the removed `severity_override` field broke demo installs).

### 19.0.2.0.2

- fix(security): grant `group_hazard_viewer` to spp_user_roles roles (Registry Viewer, Program Manager, Global/Local Registrar) that the OP#951 menu audit identifies as needing read-only Hazard menu access. Other affected roles defined outside this module (program/CR/farm roles) are wired in their own modules.
- fix(views): gate the "Hazard and Emergency" top-level menu (`hazard_main_menu_root`) on `group_hazard_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Global Finance, Global Support, Global Support Manager, Local Support).

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the hazard impacts list on registrant forms, and hide the table when empty (showing a muted info line instead) (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
