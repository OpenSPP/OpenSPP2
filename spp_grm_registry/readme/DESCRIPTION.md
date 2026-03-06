Links GRM (Grievance Redress Mechanism) tickets to OpenSPP registrants (individuals and households). Automatically detects repeat tickets from the same registrant within a six-month window and displays previous ticket history on both ticket and registrant forms.

### Key Capabilities

- Link tickets to individual registrants (`registrant_id`) and households (`household_id`)
- Auto-populate ticket fields: when registrant is selected, fills `partner_id`, `area_id`, and `household_id` from registrant data
- Detect repeat tickets: compute `is_repeat` and `repeat_count` for tickets filed by the same registrant in last 6 months
- Display warning banner and previous tickets button on ticket form when `is_repeat=True`
- Track ticket counts on registrant profiles with smart buttons (total and open counts)
- Filter tickets by registrant, household, area, or repeat status

### Key Models

| Model            | Description                                                 |
| ---------------- | ----------------------------------------------------------- |
| `spp.grm.ticket` | Adds registrant/household links, repeat detection fields    |
| `res.partner`    | Adds GRM ticket relationships and computed count fields     |

### UI Location

**Ticket Form** (Helpdesk > Tickets):
- Registrant, household, and area fields appear after `partner_id`
- Warning banner displays when `is_repeat=True`
- "Previous Tickets" button in header (visible when `repeat_count > 0`)
- "Previous Tickets" tab in notebook (visible when `repeat_count > 0`)

**Registrant Form**:
- Smart button: "GRM Tickets" displays `grm_registrant_ticket_count` for individuals
- Smart button: "GRM Tickets" displays `grm_household_ticket_count` for households
- "GRM Tickets" tab shows ticket list for both individuals and households

**Search View**:
- Filters: "Repeat Tickets", "Has Registrant", "Has Household"
- Group By: Registrant, Household, Area, Repeat Status

### Behavior

**On registrant selection**:
1. Sets `partner_id` to the selected registrant
2. Populates `area_id` from registrant's geographic area (if available)
3. Auto-fills `household_id` with registrant's first household membership (if member of a group)

**On household selection**:
- Filters registrant dropdown to show only members of that household

**Repeat detection** (computed on create/write):
- Counts tickets from same registrant created in last 6 months
- Sets `is_repeat=True` if count > 0
- Populates `previous_ticket_ids` with matching tickets

### Security

No access rules defined in this module. Inherits all permissions from `spp_grm` and `spp_registry`.

### Dependencies

`spp_security`, `spp_grm`, `spp_registry`
