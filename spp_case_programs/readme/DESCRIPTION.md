Links case management to program enrollments and tracks program-triggered cases. Automatically loads program membership information when a client is selected for a case and computes enrollment status fields. Auto-installs when both `spp_case_base` and `spp_programs` are present.

### Key Capabilities

- Link cases to program enrollments via `program_membership_ids` Many2many relationship
- Track which program triggered case creation via `triggered_by_program_id` field
- Automatically load client program memberships on partner selection
- Compute enrollment status: active enrollment flag, enrollment count, enrolled program names
- Filter and group cases by enrollment status and triggering program
- View program enrollment details directly from case form

### Key Models

This module extends existing models and does not introduce new ones.

| Model      | Extension                                                                               |
| ---------- | --------------------------------------------------------------------------------------- |
| `spp.case` | Adds `program_membership_ids`, `triggered_by_program_id`, and computed enrollment fields |

### Configuration

No configuration required. Module auto-installs when both `spp_case_base` and `spp_programs` are installed.

### UI Location

This module extends the existing case form view. No standalone menus are added.

- **Form View**: Accessed via existing case management. Adds Programs tab, smart button, and header field.
- **Programs Tab**: Displays enrollment summary (has_active_enrollment, active_program_count, enrolled_program_names) and membership list with state badges
- **Smart Button**: Programs count button (visible when active_program_count > 0)
- **Header Field**: "Triggered By Program" field appears after priority
- **Search Filters**: "Has Active Enrollment", "No Active Enrollment", "Triggered by Program"
- **List View**: Active program count column
- **Kanban View**: Program enrollment icon and count in bottom-left corner

### Security

| Group                              | Access                              |
| ---------------------------------- | ----------------------------------- |
| `spp_case_base.group_case_officer` | Read/Write/Create (no delete)       |
| `spp_case_base.group_case_manager` | Full CRUD                           |

### Extension Points

- Override `_compute_program_info()` to customize enrollment status computation logic
- Override `_onchange_partner_programs()` to filter which memberships load automatically
- Inherit `spp.case` to add additional program-related fields or methods

### Dependencies

`spp_security`, `spp_case_base`, `spp_programs`
