### 19.0.2.0.3

- fix(security): remove the `base.group_user` read grant on `spp.hazard.impact` so registrant-linked impact records (name, damage level, verification, notes) are readable only by hazard roles, `registry_viewer`, and admins — not every internal user via RPC. Gate the impact UI on the registrant and incident forms (stat buttons, Emergency Response / Impacts pages, list columns, search filters) to users with impact read.
- fix(security): guard `spp.hazard.incident.affected_registrant_count` with field-level `groups=`. `spp.hazard.incident` stays broadly readable (sibling modules read incidents), but this aggregate is derived from the sensitive impact table via raw ACL-bypassing SQL, so a plain internal user could read the affected-registrant count over RPC even without impact read. The field is now restricted to hazard read / `registry_viewer` / admin, which also strips it from the incident list column for other users.

### 19.0.2.0.2

- fix(security): grant `group_hazard_viewer` to spp_user_roles roles (Registry Viewer, Program Manager, Global/Local Registrar) that the OP#951 menu audit identifies as needing read-only Hazard menu access. Other affected roles defined outside this module (program/CR/farm roles) are wired in their own modules.
- fix(views): gate the "Hazard and Emergency" top-level menu (`hazard_main_menu_root`) on `group_hazard_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Global Finance, Global Support, Global Support Manager, Local Support).

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the hazard impacts list on registrant forms, and hide the table when empty (showing a muted info line instead) (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
