# OpenSPP Case Programs Integration

This module links cases to OpenSPP programs and provides compliance tracking functionality.

## Features

### Program Integration

- Links cases to program enrollments (Many2many relationship)
- Tracks which program triggered case creation
- Automatic loading of program memberships when client is selected

### Computed Fields

- **Has Active Enrollment**: Boolean indicating if client has active program enrollments
- **Active Program Count**: Count of active program enrollments
- **Enrolled Program Names**: Comma-separated list of enrolled program names

### User Interface Enhancements

#### Form View

- **Smart Button**: Shows count of active program enrollments, opens detailed view
- **Programs Tab**:
  - Summary statistics (active enrollments, program count)
  - List of program enrollments with color coding by status
  - Quick action buttons
- **Triggered By Program**: Field in header to track which program triggered the case

#### List View

- Shows active program count column

#### Kanban View

- Displays program enrollment count with graduation cap icon

#### Search & Filters

- Filter by active enrollment status
- Filter by triggered by program
- Search by program name
- Group by triggered program

### Status Color Coding

Program enrollment states are color-coded in the tree view:

- **Green**: Enrolled
- **Yellow**: Paused
- **Gray**: Exited or Not Eligible
- **Red**: Duplicated

## Technical Details

### Model Extension

Extends `spp.case` model with:

- `program_membership_ids`: Many2many to `spp.program_membership`
- `triggered_by_program_id`: Many2one to `spp.program`
- Computed fields for enrollment statistics

### Dependencies

- `spp_case_base`: Core case management functionality
- `spp_programs_base`: Core program management functionality

### Security

Uses existing case security groups:

- `spp_case_base.group_case_officer`: Read, Write, Create
- `spp_case_base.group_case_manager`: Full access including Delete

## Usage

### Creating Program-Related Cases

1. When creating a case, the system automatically loads program enrollments for the selected client
2. Optionally specify which program triggered the case creation

### Viewing Program Information

- Use the smart button to view all program enrollments
- Access the Programs tab for detailed enrollment information
- Filter cases by program enrollment status

### Tracking Compliance

- Monitor active program enrollments directly from cases
- Identify cases without active program enrollments
- Track program-triggered cases for compliance monitoring

## Installation

1. Install module dependencies: `spp_case_base` and `spp_programs_base`
2. Install this module
3. No additional configuration required

## Author

OpenSPP

## License

LGPL-3
