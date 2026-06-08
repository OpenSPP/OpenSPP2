Tracks attendance at required sessions and trainings for social protection programs. Records participant attendance, computes attendance rates against expected participation, and manages session lifecycle from scheduling through completion. Supports conditional cash transfer programs requiring minimum attendance thresholds.

### Key Capabilities

- Define session types with attendance requirements and frequency (weekly, biweekly, monthly, quarterly, one-time)
- Schedule sessions with facilitators, co-facilitators, location, and expected participants
- Record attendance with timestamps, excused absences, and notes
- Compute attendance rates and track attendance counts automatically
- Track topics covered in each session (optional, configurable per session type)
- Manage session state: scheduled → in progress → completed → cancelled
- Filter sessions by facilitator, type, state, and date range
- View sessions in list, form, calendar (by date), or kanban (grouped by state)

### Key Models

| Model                     | Description                                              |
| ------------------------- | -------------------------------------------------------- |
| `spp.session.type`        | Session type definition with attendance requirements     |
| `spp.session.topic`       | Topics that can be covered in sessions                   |
| `spp.session`             | Session instance with facilitator, participants, and date |
| `spp.session.attendance`  | Attendance record for a participant at a session         |

### Configuration

After installing:

1. Navigate to **Session Tracking > Configuration > Session Types**
2. Review pre-configured session types (Training, Family Development Session, Group Meeting, Workshop)
3. Add or modify session types as needed; topics are managed within each session type form when topic tracking is enabled
4. Adjust required attendance percentage per session type

Four session types are pre-configured with sample topics for Family Development Sessions and Training Sessions.

### UI Location

- **Menu**: Session Tracking > Sessions > All Sessions
- **My Sessions**: Session Tracking > Sessions > My Sessions (filtered to current user as facilitator)
- **Configuration**: Session Tracking > Configuration > Session Types (managers only)
- **Views**: List, form, calendar (by date), kanban (grouped by state), graph, pivot

### Security

| Group                                          | Access                                |
| ---------------------------------------------- | ------------------------------------- |
| `spp_session_tracking.group_session_user`      | Read all sessions and session types/topics; create/write own facilitated or co-facilitated sessions; read/write/create attendance for own sessions (no delete) |
| `spp_session_tracking.group_session_manager`   | Full CRUD on all sessions, types, topics, and attendance |

The session user group can view all sessions but only edit sessions where they are the facilitator or co-facilitator (via record rules). Session creation requires manager access. The `spp_security.group_spp_admin` group implies manager access. Multi-company record rules ensure users only see sessions belonging to their company.

### Extension Points

- Inherit `spp.session.type` to add custom fields for program-specific session metadata
- Inherit `spp.session.attendance` to track additional compliance data
- Override `_compute_attendance()` on `spp.session` to customize attendance rate calculations

### Dependencies

`base`, `mail`, `spp_area`, `spp_security`
