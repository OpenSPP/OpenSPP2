No-code event type designer for defining custom data collection forms. Allows users to create event types through a 3-step wizard, defining fields with validation rules and conditional visibility. Generated event types integrate with `spp.event.data` for recording events against registrants.

### Key Capabilities

- Create event types through a 3-step wizard (basic info, fields, review)
- Define custom fields with 10 field types: text, long text, integer, decimal, date, datetime, boolean, selection, multi-select, link
- Apply field validation rules: range constraints for numbers, regex patterns for text
- Configure conditional field visibility based on other field values
- Group fields into tabs for organized data entry forms
- Apply reusable field templates to accelerate event type creation
- Generate dynamic data entry wizards with proper widgets for each field type
- Target events to individuals, groups, or both
- Draft/Active lifecycle prevents editing active event types
- Optional Kobo form integration for external data collection
- Optional approval workflow configuration

### Key Models

| Model                                   | Description                                                 |
| --------------------------------------- | ----------------------------------------------------------- |
| `spp.studio.event.type`                 | Custom event type definition with draft/active lifecycle   |
| `spp.studio.event.field`                | Field definition with type, validation, and visibility      |
| `spp.studio.event.field.group`          | Groups fields into tabs in the data entry wizard           |
| `spp.studio.event.field.template`       | Reusable template containing field definitions              |
| `spp.studio.event.field.template.line`  | Field definition within a template                          |
| `spp.studio.event.type.wizard`          | 3-step wizard for creating event types                      |
| `spp.event.data.entry.wizard`           | Generated wizard for entering event data                    |

### Configuration

After installing:

1. Navigate to **Studio > Forms & Fields > Event Types**
2. Click **Create** to open the 3-step event type builder wizard
3. Define event type name, description, and target type (individual/group/both)
4. Add fields with labels, types, and validation rules
5. Review and save as draft
6. Activate the event type to enable data entry

### UI Location

- **Menu**: Studio > Forms & Fields > Event Types
- **Wizard**: 3-step builder accessed via Create button
- **Data Entry**: Generated wizard form specific to each event type, launched from event type form or registrant profile

### Security

| Group                                    | Access                                                 |
| ---------------------------------------- | ------------------------------------------------------ |
| `spp_studio.group_studio_viewer`         | Read event types and templates                         |
| `spp_studio.group_studio_editor_officer` | Read/Write/Create on event types, fields, and templates (no delete on event types/fields/templates) |
| `spp_studio.group_studio_manager`        | Full CRUD                                              |

### Extension Points

- Override `_generate_wizard_view()` on `spp.studio.event.type` to customize generated wizard form layout
- Inherit `spp.studio.event.field` and override `validate_value()` to add custom validation logic
- Extend `spp.event.data.entry.wizard` to add pre-save hooks for event data processing
- Create predefined field templates via data files in `data/event_field_templates.xml`

### Dependencies

`spp_studio`, `spp_event_data`
