### 19.0.2.0.1

- fix(security): add `groups="base.group_system"` to the existing `<menuitem id="base.menu_management" />` override in `views/main_view.xml`. Out of the box the Apps top-level menu has no group restriction and is visible to every logged-in user, violating the OP#951 audit's `Apps: no` rows. The override here is the single authoritative declaration for this menu's attributes in the OpenSPP install (sequence, custom OpenSPP icon, and now group_ids); doing the gating anywhere upstream (e.g. a `post_init_hook` in `spp_security`) is unreliable because this `<menuitem>` reload re-writes the record without a `groups` attribute and resets `group_ids` to empty.

### 19.0.2.0.0

- Initial migration to OpenSPP2
