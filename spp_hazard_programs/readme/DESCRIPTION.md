Links hazard incidents to emergency response programs. Enables programs to target affected populations using verified impact data, filter registrants by damage severity, and automatically enable emergency mode when responding to active incidents.

### Key Capabilities

- Link programs to one or more hazard incidents via many-to-many relation
- Automatically flag programs as emergency when linked to incidents in alert/active/recovery status
- Filter eligible registrants by damage level threshold (any, moderate+, severe+, critical only)
- Count affected registrants based on verified impacts matching damage criteria
- Track which programs are responding to each incident (bidirectional navigation)

### Key Models

| Model                       | Description                                          |
| --------------------------- | ---------------------------------------------------- |
| `spp.program` (extend)      | Adds target incidents, emergency mode, damage filter |
| `spp.hazard.incident` (extend) | Adds reverse relation to response programs        |

### UI Location

- **Programs**: Programs > Programs > "Emergency Response" tab
- **Incidents**: Hazard & Emergency > Incidents > All Incidents > "Response Programs" tab
- **Stat buttons**: Programs show incident count and affected registrant count; incidents show response program count
- **Filters**: "Emergency Programs" and "Has Target Incidents" filters in program search view

### Security

No new ACL entries. Access inherited from base models:

- `spp.program`: Controlled by `spp_programs` security groups
- `spp.hazard.incident`: Controlled by `spp_hazard` security groups

### Extension Points

- Override `get_emergency_eligible_registrants()` to customize eligibility logic beyond damage levels
- Override `_get_damage_level_domain()` to add custom damage filtering rules
- Inherit `spp.program` to add fields used in emergency calculations
- Use `is_emergency_program` and `is_emergency_mode` flags in downstream program logic

### Dependencies

`spp_hazard`, `spp_programs`
