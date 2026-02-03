# OpenSPP GRM Demo Data

## Overview

This module provides a comprehensive demo data generator for the OpenSPP Grievance Redress Mechanism (GRM). It uses the
scenario-based system to create realistic ticket data that simulates real-world grievance cases.

## Features

- **Scenario-Based Generation**: Leverages YAML scenario files to generate diverse, realistic GRM tickets
- **Configurable Distribution**: Control the percentage of resolved vs. open tickets
- **Workflow Simulation**: Automatically progresses tickets through resolution workflows
- **Integration**: Links tickets to existing beneficiaries and programs
- **Timeline Flexibility**: Generate tickets distributed over a customizable time period
- **Multiple Categories**: Supports various ticket categories including payments, eligibility, service delivery, and
  more

## Dependencies

- `spp_demo_common` - Core demo data infrastructure Optional: `spp_demo_scenarios` - Scenario library and loader (not
  required; falls back to built-in samples)
- `spp_grm` - Grievance Redress Mechanism module

## Installation

1. Install the module through Odoo Apps menu
2. The module will automatically create basic ticket categories
3. If installed, `spp_demo_scenarios` scenarios will be used; otherwise built-in samples are used automatically

## Usage

### Using the Wizard

1. Navigate to **GRM → Generate Demo Data** menu
2. Configure the generation parameters:

   - **Number of Tickets**: How many tickets to generate (1-10,000)
   - **Days Back**: Distribute tickets over the last N days
   - **Scenarios**: Select specific scenarios or use all available
   - **Resolved %**: Percentage of tickets to mark as resolved
   - **Escalated %**: Percentage of unresolved tickets to escalate
   - **Link to Beneficiaries**: Whether to link tickets to registrants
   - **Link to Programs**: Whether to reference programs in tickets

3. Click **Generate Tickets** to create the demo data
4. View the generated tickets in the GRM tickets list

### Programmatic Usage

You can also use the generator programmatically:

```python
# Create generator
generator = env['spp.grm.demo.generator'].create({
    'name': 'My Demo Data',
    'number_of_tickets': 100,
    'tickets_days_back': 60,
    'resolved_percentage': 70.0,
    'link_to_beneficiaries': True,
    'link_to_programs': True,
})

# Generate tickets
action = generator.generate_tickets()
```

## Scenarios

If present, the module can consume scenario files from `spp_demo_scenarios/scenarios/grm/` which define:

- **Ticket Profiles**: Category, priority, expected resolution time
- **Description Templates**: Realistic ticket descriptions with placeholders
- **Resolution Paths**: Different ways tickets can be resolved
- **Timeline Events**: Workflow progression steps

### Available Scenarios

The following scenarios are included:

- **Payment Issues**

  - `payment_not_received.yaml` - Beneficiary didn't receive payment
  - `payment_wrong_amount.yaml` - Incorrect payment amount

- **Eligibility Disputes**

  - `eligibility_dispute.yaml` - Questioning eligibility decisions

- **Service Quality**

  - `service_quality.yaml` - Complaints about service delivery

- **Information Requests**

  - `information_request.yaml` - General information queries

- **Data Updates**

  - `update_personal_info.yaml` - Requests to update beneficiary data

- **Case Escalations**
  - `case_eligibility_review.yaml` - Complex eligibility cases
  - `case_payment_investigation.yaml` - Detailed payment investigations

## Cross-Module Integration

### Shared Personas with MIS and Case Management

The GRM demo uses the same personas as `spp_mis_demo_v2` and `spp_case_demo` for consistent cross-module demos:

| Persona          | GRM Ticket                | MIS Program              | Case                     |
| ---------------- | ------------------------- | ------------------------ | ------------------------ |
| Juan Dela Cruz   | Payment not received      | Cash Transfer Program    | Dela Cruz Emergency      |
| Fatima Al-Rahman | Eligibility inquiry       | Universal Child Grant    | Al-Rahman Assessment     |
| Ibrahim Hassan   | Resettlement support      | Emergency Relief Fund    | Hassan Resettlement      |
| Ahmed Said       | Multiple tickets (3)      | Cash Transfer Program    | Said Family Support      |
| David Martinez   | Grant application status  | Disability Support Grant | Martinez Disability      |
| Maria Santos     | Graduation inquiry        | Cash Transfer Program    | Santos Family Support    |
| Rosa Garcia      | Food delivery schedule    | Elderly Pension + Food   | Garcia Elder Care        |
| Carlos Morales   | Adding new child to grant | Universal Child Grant    | Morales Household Crisis |

### GRM-to-Case Escalation

Story tickets can be marked for case escalation (`escalate_to_case: True`), demonstrating:

- **Payment Issues**: Juan Dela Cruz emergency → Case management for comprehensive support
- **Eligibility Inquiries**: Fatima Al-Rahman → Proactive case assessment
- **Complex Needs**: Ibrahim Hassan resettlement → Multi-service coordination
- **Pattern Detection**: Ahmed Said repeat tickets → Root cause case management
- **Disability Support**: David Martinez → Equipment and education coordination

### Recommended Demo Order

For comprehensive cross-module demos:

1. Run `spp_demo` story generation (creates registrants)
2. Run `spp_mis_demo_v2` (creates programs and enrollments)
3. Run `spp_grm_demo` (creates GRM tickets referencing programs)
4. Run `spp_case_demo` (creates cases linked to GRM tickets)

## Data Generated

For each ticket, the generator creates:

1. **Basic Ticket Information**

   - Title (derived from scenario)
   - Description (from scenario templates with realistic data)
   - Creation date (random within specified range)
   - Priority (based on scenario profile)

2. **Links and References**

   - Beneficiary (random registrant)
   - Program (if applicable)
   - Category (from scenario)
   - Channel (random submission channel)

3. **Workflow Progression**

   - Resolution notes (for closed tickets)
   - Escalation notes (for escalated tickets)
   - Assignment to users
   - Stage transitions with proper dates

4. **Realistic Details**
   - Generated using Faker library
   - Locale-aware (based on company country)
   - Context-appropriate placeholders (dates, amounts, etc.)

## Configuration

### Ticket Categories

The module creates the following default categories:

- Payment Issues
- Eligibility Questions
- Service Delivery
- Information Requests
- Data Update Requests
- General
- Complaint
- Feedback

These can be extended or modified through the GRM configuration.

### Scenario Selection

You can select specific scenarios in the wizard, or leave the selection empty to use all available GRM ticket scenarios.
The generator uses weighted random selection based on the `weight` field in each scenario file.

## Prerequisites

Before generating GRM demo data:

1. **Beneficiaries Required**: The system must have registrants (beneficiaries) created. Use the base demo data
   generator to create registrants first.

2. **GRM Configuration**: Ensure the GRM module is properly configured with:

   - Ticket stages
   - Ticket channels (email, phone, portal, etc.)
   - Basic GRM settings

3. **Optional Programs**: If linking to programs, create some programs first using the program management module.

## Technical Details

### Models

- `spp.grm.demo.generator` - Transient model containing the generation logic
- `spp.grm.demo.wizard` - Wizard interface inheriting from the generator

### Key Methods

- `generate_tickets()` - Main entry point for ticket generation
- `_create_ticket_from_scenario()` - Creates individual ticket from scenario
- `_simulate_ticket_workflow()` - Progresses ticket through workflow
- `_render_description_template()` - Fills in scenario template placeholders

### Workflow Simulation

The generator simulates realistic ticket workflows:

1. **Creation**: Ticket created with random date in range
2. **Assignment**: May be assigned to a user
3. **Resolution** (for resolved tickets):

   - Selects resolution path from scenario
   - Adds notes for each resolution step
   - Moves to closed stage
   - Backdates all actions appropriately

4. **Escalation** (for some open tickets):
   - Adds escalation note
   - References case type from scenario

## Troubleshooting

### No tickets generated

- **Error**: "No beneficiaries (registrants) found"

  - **Solution**: Create registrants first using `spp_base_demo` or similar

- **Error**: "No scenarios found"
  - **Solution**: Install `spp_demo_scenarios` module (optional)

### Tickets not distributed over time

- Check that `tickets_days_back` is set to a reasonable value (e.g., 90)
- Verify the system date is correct

### Categories not found

- Run an upgrade of the module to ensure data files are loaded
- Check that `data/ticket_categories.xml` is in the manifest

## Contributing

To add new scenarios:

1. If you want custom scenarios, create a YAML file in `spp_demo_scenarios/scenarios/grm/`
2. Follow the scenario schema (see `spp_demo_common/lib/scenario_schema.py`)
3. Set `category: grm_ticket` in the scenario file
4. Include realistic description templates
5. Define resolution paths with probabilities
6. Test with the generator

## License

LGPL-3

## Credits

**Authors**: OpenSPP.org

**Maintainers**: jeremi, gonzalesedwin1123
