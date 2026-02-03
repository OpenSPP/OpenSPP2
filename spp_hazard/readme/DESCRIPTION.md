Records disaster events and tracks their impact on individual registrants. Supports hierarchical hazard classification, geographic scope tracking, severity levels, and verification workflows to enable targeted emergency response and humanitarian assistance.

### Key Capabilities

- Define hazard categories in a tree structure (e.g., Natural > Storm > Typhoon)
- Record incidents with start/end dates, severity levels, and lifecycle status (alert, active, recovery, closed)
- Link incidents to geographic areas with area-specific severity overrides
- Track registrant-level impacts by type (physical, economic, health, social) and damage level
- Verify impact records with workflow states (reported, verified, disputed, closed)
- Bulk-create impact records for all registrants in an affected area via `bulk_create_impacts()`
- Identify potentially affected registrants based on geographic location

### Key Models

| Model                      | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| `spp.hazard.category`      | Hierarchical classification of hazard types                      |
| `spp.hazard.incident`      | Specific disaster event with dates, severity, and affected areas |
| `spp.hazard.incident.area` | Links incident to area with area-specific details                |
| `spp.hazard.impact`        | Records impact on a registrant (type, damage level, verification)|
| `spp.hazard.impact.type`   | Classification of impact types by category                       |
| `res.partner` (extended)   | Adds hazard impact tracking fields to registrants                |

### Configuration

After installing:

1. Navigate to **Hazard & Emergency > Configuration > Hazard Categories**
2. Create or review hierarchical hazard categories (e.g., Natural Disasters, Man-made Disasters)
3. Navigate to **Hazard & Emergency > Configuration > Impact Types**
4. Review pre-configured impact types (Displacement, Property Damage, Injury, etc.) or create custom types

### UI Location

- **Menu**: Hazard & Emergency (top-level application menu)
- **Incidents**: Hazard & Emergency > Incidents > All Incidents
- **Impacts**: Hazard & Emergency > Incidents > Impact Records
- **Configuration**: Hazard & Emergency > Configuration (accessible to managers only)
- **Registrant Form**: Stat button shows impact count; "Emergency Response" tab displays impact records list

### Security

| Group                          | Access                                              |
| ------------------------------ | --------------------------------------------------- |
| `group_hazard_viewer`          | Read-only access to all hazard records              |
| `group_hazard_officer`         | Create and manage incidents and impacts (no delete) |
| `group_hazard_manager`         | Full CRUD access including configuration            |
| `spp_security.group_spp_admin` | Inherits manager access                             |

### Extension Points

- Inherit `spp.hazard.incident` and override `identify_potentially_affected_registrants()` to customize targeting logic
- Inherit `spp.hazard.impact` to add domain-specific impact fields (e.g., crop damage for farmer registries)
- Override `bulk_create_impacts()` to customize mass impact record creation

### Dependencies

`base`, `spp_security`, `spp_registry`, `spp_area`
