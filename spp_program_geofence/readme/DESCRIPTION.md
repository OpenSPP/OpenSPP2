# OpenSPP Program Geofence

Adds geofence-based geographic targeting to OpenSPP programs.

## Features

- **Program Geofences**: Define geographic boundaries (geofences) on programs to scope their
  geographic coverage. Geofences are configured on the program's Overview tab.

- **Geofence Eligibility Manager**: A pluggable eligibility manager that determines registrant
  eligibility based on their location relative to the program's geofences. Works alongside other
  eligibility managers using AND logic.

- **Hybrid Two-Tier Targeting**:
  - **Tier 1 (GPS)**: Matches registrants whose GPS coordinates fall within the geofence polygons.
  - **Tier 2 (Area Fallback)**: For registrants without GPS coordinates, matches those whose
    administrative area intersects the geofence. This fallback can be disabled per manager.

- **Preview**: Preview how many registrants match the current geofences before importing.

## Known Limitations

- Groups (households) typically lack GPS coordinates. Enable the area fallback to match them by
  administrative area.
- Changing geofences after enrollment does not retroactively affect existing memberships.
  Use cycle eligibility verification for ongoing checks.
- Archived geofences are excluded from spatial queries.
