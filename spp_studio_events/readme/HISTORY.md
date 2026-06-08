### 19.0.2.0.2

- fix(views): the basic Create Event wizard's step 1 is now self-explanatory for Studio-backed event types. The misleading raw JSON field is hidden; an info banner announces the next stage; the "Create Event" button is renamed "Next" so users know there's a second step where the structured fields appear. Non-Studio event types keep the original step-1 UI unchanged. Backed by a new computed `is_studio_event_type` boolean on `spp.create.event.wizard`.

### 19.0.2.0.1

- fix(views): clicking the **Events** smart button on a Studio Event Type form no longer crashes with `View types not defined tree`. `action_view_events` returned `view_mode="tree,form"`, but Odoo 19 renamed `tree` to `list`; switched to `view_mode="list,form"`.

### 19.0.2.0.0

- Initial migration to OpenSPP2
