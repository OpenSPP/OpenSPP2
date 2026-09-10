Tracks participant attendance for social protection program activities. Records presence/absence with date, time, location, and activity type. Provides OAuth-secured API endpoints for external systems to submit attendance data and import participants from external registries.

**Positioning vs `spp_session_tracking`:** this module is a standalone, API-first attendance
service — it keeps its own participant registry (synced from an external registry) and receives
attendance events from external systems over REST, so it can run on a bare instance without the
program stack. `spp_session_tracking` covers the complementary case: attendance at sessions and
trainings managed *inside* a program instance. The two do not share models and can coexist.

### Key Capabilities

- Record attendance with date, time, type, location, and category (present/absent)
- Query attendance history via `get_attendance_list()` with filtering by date range, type, and location
- Import participants from external registries via configurable field mapping
- Generate OAuth client credentials for external API access
- Enforce configurable uniqueness constraints (date/time/type/location) to prevent duplicate records

### Key Models

| Model                                  | Description                                        |
| -------------------------------------- | -------------------------------------------------- |
| `spp.attendance.subscriber`            | Participant registry, inherits res.partner         |
| `spp.attendance.list`                  | Attendance record with date, time, type, location  |
| `spp.attendance.type`                  | Configurable attendance event types                |
| `spp.attendance.location`              | Configurable attendance locations                  |
| `spp.attendance.api.client.credential` | OAuth credentials for external API clients         |
| `spp.import.attendance.wizard`         | Wizard for importing from external registries      |

### Configuration

After installing:

1. Navigate to **Settings > SPP Attendance Settings** to configure:
   - Uniqueness constraints (date/time/type/location)
   - Server URL and API endpoints
   - Field mappings for import (personal information, identifiers, contact details)
2. Create attendance types: **Attendance > Configuration > Attendance Type**
3. Create locations: **Attendance > Configuration > Attendance Location**
4. Generate OAuth credentials: **Settings > Attendance API Client Credentials**

### UI Location

- **Main Menu**: Attendance > Subscriber
- **Configuration**: Attendance > Configuration (Attendance Type, Attendance Location)
- **API Credentials**: Settings > Attendance API Client Credentials
- **Settings**: Settings > SPP Attendance Settings
- **Subscriber Form**: Contains "Attendance" and "Person Information" tabs

### Security

| Group                                    | Access    |
| ---------------------------------------- | --------- |
| `spp_attendance.group_attendance_viewer` | Read      |
| `spp_attendance.group_attendance_manager` | Full CRUD |

### Extension Points

- Override `get_attendance_list()` on `spp.attendance.subscriber` to customize attendance queries
- Inherit `spp.attendance.list` to add domain-specific attendance metadata
- Extend `_import_attendance()` in wizard to customize import logic

### Dependencies

`base`, `spp_oauth`, `spp_security`
