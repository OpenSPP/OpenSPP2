### 19.0.2.0.1

- fix(security): gate the Odoo-stock **Apps** top-level menu (`base.menu_management`) on `base.group_system`. Out of the box the menu had no `groups` restriction and was visible to every logged-in user, so the OP#951 audit's `Apps: no` rows were silently violated. System Admin is the only OpenSPP role that pulls in `base.group_system`, so this single override hides Apps from every other role without touching any individual role definition.

### 19.0.2.0.0

- Initial migration to OpenSPP2
