Bridge module linking GRM tickets to program records. Auto-installs when both `spp_grm` and `spp_programs` are present. Enables tracking of program-specific grievances through relational links to programs, enrollments, cycles, entitlements, and payments with automatic field population and computed status/amount displays.

### Key Capabilities

- Link tickets to programs, enrollments, cycles, entitlements, and payments via Many2one fields
- Auto-populate related fields based on record relationships (selecting payment fills entitlement, cycle, and registrant)
- Display computed enrollment status and monetary amounts from linked records
- Navigate to program records via stat buttons on ticket form
- Filter and group tickets by program, cycle, or enrollment status

### Models Extended

| Model            | Description                                   |
| ---------------- | --------------------------------------------- |
| `spp.grm.ticket` | Adds 5 relational and 3 computed program fields |

### New Fields on `spp.grm.ticket`

**Relational fields:**
- `program_id` → `spp.program`
- `program_membership_id` → `spp.program.membership`
- `cycle_id` → `spp.cycle`
- `entitlement_id` → `spp.entitlement`
- `payment_id` → `spp.payment`

**Computed fields (stored):**
- `enrollment_status`: Current state from program membership
- `entitlement_amount`: Amount from linked entitlement
- `payment_amount`: Amount from linked payment

### UI Location

- **Menu**: Helpdesk > Tickets (no new menus, extends existing ticket views)
- **Form**: "Program Information" section below ticket details with stat buttons for linked records
- **Search**: Filters for "Has Program", "Has Entitlement", "Has Payment"; group by Program, Cycle, Enrollment Status
- **Tree/Kanban**: Program fields available as optional columns and card elements

### Security

No additional access rules defined. Inherits all security from `spp_grm`. Users with read/write access to GRM tickets can read/write program links.

### Extension Points

- Override `_compute_program_info()` to customize enrollment status and amount extraction logic
- Extend `_onchange_*` methods to add domain-specific auto-fill behavior

### Dependencies

`spp_security`, `spp_grm`, `spp_programs`
