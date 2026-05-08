### 19.0.2.0.1

- fix(views): clicking the **Events** smart button on a Studio Event Type form no longer crashes with `View types not defined tree`. `action_view_events` returned `view_mode="tree,form"`, but Odoo 19 renamed `tree` to `list`; switched to `view_mode="list,form"`.

### 19.0.2.0.0

- Initial migration to OpenSPP2
