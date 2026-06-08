### 19.0.2.0.2

- fix(security): grant `group_hazard_viewer` to spp_user_roles roles (Registry Viewer, Program Manager, Global/Local Registrar) that the OP#951 menu audit identifies as needing read-only Hazard menu access. Other affected roles defined outside this module (program/CR/farm roles) are wired in their own modules.
- fix(views): gate the "Hazard and Emergency" top-level menu (`hazard_main_menu_root`) on `group_hazard_viewer`. Previously the root menu had no `groups=` attribute and was visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Global Finance, Global Support, Global Support Manager, Local Support).

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the hazard impacts list on registrant forms, and hide the table when empty (showing a muted info line instead) (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
