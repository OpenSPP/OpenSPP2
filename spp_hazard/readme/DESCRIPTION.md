Records disaster events and tracks their impact on registrants. Provides hierarchical hazard
classification, geographic scope tracking via areas and GIS geofences, severity levels, and
verification workflows to enable targeted emergency response and humanitarian assistance. Incident
and impact records include full chatter integration for audit trails and activity scheduling.

### Key Capabilities

- Define hazard categories in a tree structure (e.g., Natural > Storm > Typhoon)
- Record incidents with start/end dates, severity levels, and lifecycle status (alert, active, recovery, closed)
- Link incidents to geographic areas with area-specific severity overrides
- Define hazard zone geofences linked to specific incidents via `spp.gis.geofence` extension
- Track registrant-level impacts by type (physical, economic, health, social) and damage level
- Verify impact records with workflow states (reported, verified, disputed, closed)
- Bulk-create impact records for all registrants in an affected area via `bulk_create_impacts()`
- Identify potentially affected registrants based on geographic location

### Key Models

| Model                        | Description                                                      |
| ---------------------------- | ---------------------------------------------------------------- |
| `spp.hazard.category`        | Hierarchical classification of hazard types                      |
| `spp.hazard.incident`        | Specific disaster event with dates, severity, and affected areas |
| `spp.hazard.incident.area`   | Links incident to area with area-specific severity override      |
| `spp.hazard.impact`          | Records impact on a registrant (type, damage level, verification)|
| `spp.hazard.impact.type`     | Classification of impact types by category                       |
| `res.partner` (extended)     | Adds hazard impact tracking fields to registrants                |
| `spp.gis.geofence` (extended)| Adds `hazard_zone` geofence type and incident linking            |

### Configuration

After installing:

1. Navigate to **Hazard and Emergency > Configuration > Hazard Categories**
2. Create or review hierarchical hazard categories (e.g., Natural Disasters, Man-made Disasters)
3. Navigate to **Hazard and Emergency > Configuration > Impact Types**
4. Review pre-configured impact types (Displacement, Property Damage, Injury, etc.) or create custom types

### UI Location

- **Menu**: Hazard and Emergency (top-level application menu)
- **Incidents**: Hazard and Emergency > Incidents > All Incidents
- **Impacts**: Hazard and Emergency > Incidents > Impact Records
- **Configuration**: Hazard and Emergency > Configuration (accessible to managers only)
- **Registrant Form**: Stat button shows impact count; "Emergency Response" tab displays impact records list

### Security

| Group                          | Access                                                            |
| ------------------------------ | ----------------------------------------------------------------- |
| `group_hazard_viewer`          | Read-only access to all hazard records                            |
| `group_hazard_officer`         | Read/write/create incidents and impacts (no delete)               |
| `group_hazard_manager`         | Full CRUD access including configuration models                   |
| `spp_security.group_spp_admin` | Inherits manager access                                           |

### Extension Points

- Inherit `spp.hazard.incident` and override `identify_potentially_affected_registrants()` to customize targeting logic
- Inherit `spp.hazard.impact` to add domain-specific impact fields (e.g., crop damage for farmer registries)
- Override `bulk_create_impacts()` to customize mass impact record creation
- Extend `spp.gis.geofence` to add behavior for `hazard_zone` geofence type

### Dependencies

`base`, `spp_security`, `spp_registry`, `spp_area`, `spp_gis`
