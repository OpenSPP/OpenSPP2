### 19.0.2.0.1

- fix(views): the **Event Data** button on the registrant form now opens the Studio-aware entry wizard (`spp.event.data.entry.wizard`) when any active Studio event type matches the registrant's target type (individual / group / both). Previously the button always opened the basic wizard (`spp.create.event.wizard`), which exposes a raw JSON input field and ignores Studio-defined fields. Falls back to the basic wizard when no Studio types apply, preserving the legacy entry path.
- fix(views): clicking the **Events** smart button on a Studio Event Type form no longer crashes with `View types not defined tree`. `action_view_events` returned `view_mode="tree,form"`, but Odoo 19 renamed `tree` to `list`; switched to `view_mode="list,form"`.

### 19.0.2.0.0

- Initial migration to OpenSPP2
