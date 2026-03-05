# OpenSPP GRM Programs Integration

This module integrates the OpenSPP Grievance Redress Mechanism (GRM) with the Programs
module, allowing GRM tickets to be linked to programs, entitlements, and payments.

## Features

### Program Linkage

- Link GRM tickets to specific programs
- Link to program memberships (enrollments)
- Link to specific program cycles
- Link to entitlements being disputed
- Link to payments being disputed

### Auto-fill Functionality

- When a registrant and program are selected, automatically finds and suggests the
  program membership
- When a membership is selected, automatically fills the program and registrant
- When a cycle is selected, automatically fills the program
- When an entitlement is selected, automatically fills the cycle, program, and
  registrant
- When a payment is selected, automatically fills the entitlement, cycle, and registrant

### Computed Information

- Display enrollment status from program membership
- Display entitlement amount
- Display payment amount

### Enhanced Views

- Added "Program Information" section in ticket form view
- Added stat buttons to quickly navigate to related program, entitlement, or payment
- Added program-related fields to tree view (optional columns)
- Added search filters for tickets with programs, entitlements, or payments
- Added group by options for program, cycle, and enrollment status
- Display program information in kanban cards

## Dependencies

- `spp_grm`: Base GRM module
- `spp_programs_base`: Base programs module

## Usage

### Creating a Program-Related Ticket

1. Create or edit a GRM ticket
2. In the "Program Information" section, select the related program
3. Optionally select the program membership, cycle, entitlement, or payment
4. The system will auto-fill related fields based on your selection

### Viewing Related Records

- Use the stat buttons in the ticket header to quickly navigate to the related program,
  entitlement, or payment
- The computed fields show key information without needing to open the related records

### Filtering and Grouping

- Use the search filters to find tickets related to programs, entitlements, or payments
- Group tickets by program, cycle, or enrollment status for better organization

## Technical Details

### Model Extensions

- Extends `spp.grm.ticket` with the following fields:
  - `program_id`: Many2one to `spp.program`
  - `program_membership_id`: Many2one to `spp.program_membership`
  - `cycle_id`: Many2one to `spp.cycle`
  - `entitlement_id`: Many2one to `spp.entitlement`
  - `payment_id`: Many2one to `spp.payment`
  - `enrollment_status`: Computed Char field
  - `entitlement_amount`: Computed Float field
  - `payment_amount`: Computed Float field

### Methods

- `_compute_program_info()`: Computes enrollment status and amounts
- `_onchange_program_membership()`: Auto-fills membership
- `_onchange_membership()`: Auto-fills program and registrant
- `_onchange_cycle()`: Auto-fills program
- `_onchange_entitlement()`: Auto-fills cycle, program, and registrant
- `_onchange_payment()`: Auto-fills entitlement, cycle, and registrant
- `action_view_program()`: Opens the related program form
- `action_view_entitlement()`: Opens the related entitlement form
- `action_view_payment()`: Opens the related payment form

## License

LGPL-3

## Author

OpenSPP.org
