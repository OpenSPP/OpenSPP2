### 19.0.2.0.2

- fix(security): the Tier-3 `group_registry_read` group can read the consent models the registrant form depends on. This module extends that form, and its models were granted only to the Tier-2 `group_registry_viewer` group, so a Tier-3-scoped role hit an AccessError opening a registrant. The two wizard models are deliberately not included: their entry points are restricted to the officer and manager tiers, so read access would grant nothing usable while exposing other users' in-progress wizard rows.

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the Consents list on registrant forms, and hide the table entirely when there are no consents (showing a muted info line instead) — matches the empty-state treatment of read-only / no-create lists elsewhere (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
