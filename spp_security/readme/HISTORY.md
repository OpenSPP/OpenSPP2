### 19.0.2.0.1

- fix(security): gate the Odoo-stock **Apps** top-level menu (`base.menu_management`) on `base.group_system` via a new `_gate_apps_menu` hook called from `post_init_hook`. Out of the box the menu had no `groups` restriction and was visible to every logged-in user, so the OP#951 audit's `Apps: no` rows were silently violated. System Admin is the only OpenSPP role that pulls in `base.group_system`, so this single Many2many write hides Apps from every other role without touching any individual role definition. Hook is idempotent and re-applies on every install/upgrade.

### 19.0.2.0.0

- Initial migration to OpenSPP2
