Links hazard incidents to emergency response programs. Enables programs to
target affected populations using verified impact data, filter registrants
by damage severity, and flag programs as emergency when responding to
active incidents. Auto-installs when both `spp_hazard` and `spp_programs`
are present.

### Key Capabilities

- Link programs to one or more hazard incidents via many-to-many relation
- Compute `is_emergency_program` flag when any linked incident has status alert, active, or recovery
- Filter eligible registrants by damage level threshold: any, moderate+, severe+, or critical/totally damaged only
- Count affected registrants from verified `spp.hazard.impact` records matching the damage criteria
- Toggle `is_emergency_mode` to apply relaxed compliance rules during active response
- Navigate from programs to target incidents and affected registrants via stat buttons
- Navigate from incidents to response programs via stat button
- Show "Emergency Response" ribbon on program forms when `is_emergency_program` is true

### Key Models

| Model                            | Description                                                        |
| -------------------------------- | ------------------------------------------------------------------ |
| `spp.program` (extend)           | Adds `target_incident_ids`, `is_emergency_program`, `is_emergency_mode`, `qualifying_damage_levels` |
| `spp.hazard.incident` (extend)   | Adds `program_ids` reverse relation and `program_count`            |

### UI Location

- **Programs form**: Programs > Programs > "Emergency Response" tab
- **Incidents form**: Hazard and Emergency > Incidents > All Incidents > "Response Programs" tab (visible when programs linked)
- **Stat buttons**: Program form shows incident count and affected registrant count; incident form shows response program count
- **List views**: Program list adds "Emergency" column; incident list adds "Programs" column
- **Filters**: "Emergency Programs" and "Has Target Incidents" in program search view

### Security

No new models or ACL entries. Fields added to existing models inherit access from:

- `spp.program`: Controlled by `spp_programs` security groups
- `spp.hazard.incident`: Controlled by `spp_hazard` security groups

### Extension Points

- Override `get_emergency_eligible_registrants()` to customize eligibility logic beyond damage levels
- Override `_get_damage_level_domain()` to add custom damage filtering rules
- Inherit `spp.program` to add fields used in emergency calculations
- Use `is_emergency_program` and `is_emergency_mode` flags in downstream program logic

### Dependencies

`spp_hazard`, `spp_programs`
