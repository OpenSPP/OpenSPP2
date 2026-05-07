### 19.0.2.0.1

- fix(views): the **Event Data** button on the registrant form now opens the Studio-aware entry wizard (`spp.event.data.entry.wizard`) when any active Studio event type matches the registrant's target type (individual / group / both). Previously the button always opened the basic wizard (`spp.create.event.wizard`), which exposes a raw JSON input field and ignores Studio-defined fields. Falls back to the basic wizard when no Studio types apply, preserving the legacy entry path.

### 19.0.2.0.0

- Initial migration to OpenSPP2
