Connects Grievance Redress Mechanism (GRM) tickets with Case Management cases to enable escalation workflows. When a ticket requires intensive intervention, staff escalate it via a wizard that creates a linked case, assigns workers, and optionally closes the ticket. Cases can generate follow-up tickets for ongoing grievance tracking.

### Key Capabilities

- Escalate GRM tickets to case management cases via wizard with configurable case type, intensity, and assignment
- Bidirectional linking: tickets track their related case, cases track all related tickets
- Smart buttons on ticket and case forms show linked records and allow navigation
- Automatic intake source tracking (`intake_source='grm'`) for cases created from tickets
- Optional ticket closure with decision recording after escalation
- Create follow-up GRM tickets from cases for continued grievance handling
- Filter and group tickets by case linkage, cases by GRM source

### Key Models

| Model                       | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| `spp.grm.escalate.wizard`   | Transient wizard to configure and execute escalation     |
| `spp.grm.ticket` (extended) | Adds `case_id` field and escalation/view case actions    |
| `spp.case` (extended)       | Adds `source_grm_ticket_id`, `grm_ticket_ids`, and count |

### Configuration

No configuration required. Auto-installs when both `spp_grm` and `spp_case_base` are present.

### UI Location

**From GRM Ticket:**

- **Escalate button**: Ticket form header (visible when no case linked)
- **Case smart button**: Ticket form button box (visible when case linked)
- **Case section**: Embedded case details in ticket form when linked
- **Filters**: "Has Case" and "No Case" filters in ticket search view

**From Case:**

- **Create Ticket button**: Case form button box (always visible)
- **Tickets smart button**: Case form button box (shows count when tickets exist)
- **GRM Tickets tab**: Case form notebook (visible when tickets linked)
- **Source ticket field**: Case intake section when escalated from ticket

### Security

| Group                              | Access    |
| ---------------------------------- | --------- |
| `spp_grm.group_grm_user`           | Full CRUD |
| `spp_grm.group_grm_manager`        | Full CRUD |
| `spp_case_base.group_case_worker`  | Full CRUD |
| `spp_case_base.group_case_manager` | Full CRUD |

Record rules enforce that GRM users can only escalate tickets assigned to them; managers can escalate any ticket.

### Extension Points

- Override `EscalateToCaseWizard.action_escalate()` to customize case creation logic or add post-escalation hooks
- Inherit `spp.grm.ticket` to add fields exposed in the escalation wizard context
- Inherit `spp.case` to customize follow-up ticket creation via `action_create_grm_ticket()`

### Dependencies

`spp_security`, `spp_grm`, `spp_case_base`
