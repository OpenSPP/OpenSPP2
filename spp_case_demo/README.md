# OpenSPP Case Management Demo

## Overview

This module provides demo data generation for the OpenSPP Case Management system. It
creates realistic case management scenarios that integrate with MIS programs
(spp_mis_demo_v2) and GRM tickets (spp_grm_demo) for comprehensive cross-module
demonstrations.

## Features

- **Story-Based Cases**: 9 predefined case stories with memorable personas
- **Complete Case Lifecycle**: Intake → Assessment → Planning → Implementation →
  Monitoring → Closure
- **Cross-Module Integration**: Cases linked to MIS programs and GRM tickets
- **Intervention Plans**: Multi-service coordination with referrals
- **Home Visits & Notes**: Realistic case activity documentation

## Demo Stories (9 Personas)

### Primary Case Stories

| Persona          | Case Type            | Scenario                                 | Cross-Module Links            |
| ---------------- | -------------------- | ---------------------------------------- | ----------------------------- |
| Maria Santos     | General Support      | Full lifecycle - graduation success      | MIS: Cash Transfer Program    |
| Juan Dela Cruz   | Emergency Assistance | House fire displacement - high intensity | GRM: Payment ticket, MIS: CTP |
| Rosa Garcia      | Health Support       | Elderly care coordination - long-term    | MIS: Elderly Pension + Food   |
| Ana Mendoza      | Child Protection     | Child welfare - sensitive case           | -                             |
| Ibrahim Hassan   | General Support      | Displaced farmer resettlement            | GRM: Support ticket, MIS: ERF |
| Carlos Morales   | General Support      | Multi-member household crisis            | MIS: Child Grant              |
| David Martinez   | Health Support       | Disability support - wheelchair user     | GRM: Grant inquiry, MIS: DSG  |
| Fatima Al-Rahman | General Support      | GRM-initiated assessment - child grant   | GRM: Eligibility inquiry      |
| Ahmed Said       | General Support      | Repeat GRM pattern - financial literacy  | GRM: Multiple tickets         |

### Background Cases

- Fernandez Intake Pending (new intake)
- Johnson Assessment (in progress)
- Kim Case Closed (lost to follow-up)

## Cross-Module Integration

### MIS Program Integration

Cases reference specific MIS programs from `spp_mis_demo_v2`:

| Case                 | MIS Program              | Integration Point            |
| -------------------- | ------------------------ | ---------------------------- |
| Santos Family        | Cash Transfer Program    | Graduation from program      |
| Dela Cruz Emergency  | Cash Transfer Program    | Emergency payment escalation |
| Garcia Elder Care    | Elderly Pension + Food   | Multi-program coordination   |
| Hassan Resettlement  | Emergency Relief Fund    | Displacement response        |
| Morales Household    | Universal Child Grant    | Child education support      |
| Martinez Disability  | Disability Support Grant | Grant application assistance |
| Al-Rahman Assessment | Universal Child Grant    | Enrollment support           |

### GRM Integration

Cases originated from or linked to GRM tickets:

| Case                 | GRM Ticket                   | Escalation Reason             |
| -------------------- | ---------------------------- | ----------------------------- |
| Dela Cruz Emergency  | Payment not received         | Emergency requiring case mgmt |
| Hassan Resettlement  | Resettlement support request | Complex needs assessment      |
| Al-Rahman Assessment | Eligibility inquiry          | Proactive enrollment support  |
| Said Family Support  | Multiple payment tickets     | Pattern detection             |
| Martinez Disability  | Grant application status     | Comprehensive support needed  |

## Case Types

The module includes 6 case types:

| Type                   | Code | Intensity | Description            |
| ---------------------- | ---- | --------- | ---------------------- |
| General Support        | GEN  | 1         | Basic support needs    |
| Emergency Assistance   | EMG  | 3         | Urgent crisis response |
| Child Protection       | CHP  | 2         | Child welfare cases    |
| Health Support         | HLT  | 1         | Health coordination    |
| Livelihood Development | LIV  | 2         | Economic empowerment   |
| Housing Assistance     | HSG  | 2         | Housing support        |

## Case Stages

Sequential case progression:

1. **Intake** (phase=intake) - Initial case registration
2. **Assessment** (phase=assessment) - Needs evaluation
3. **Planning** (phase=planning) - Intervention planning
4. **Implementation** (phase=implementation) - Service delivery
5. **Monitoring** (phase=monitoring) - Progress tracking
6. **Closed** (phase=closure) - Case closure

## Dependencies

- `spp_demo` - Core demo data infrastructure
- `spp_case_base` - Case management module
- Optional: `spp_mis_demo_v2` - For program-linked cases
- Optional: `spp_grm_demo` - For GRM-escalated cases

## Installation

1. Install the module through Odoo Apps menu
2. Ensure `spp_demo` stories are generated first
3. For full integration, install `spp_mis_demo_v2` and `spp_grm_demo`

## Usage

### Using the Wizard

1. Navigate to **Case Management → Generate Demo Data**
2. Configure generation parameters:
   - **Number of Cases**: How many cases to generate (1-5,000)
   - **Days Back**: Distribute cases over the last N days
   - **Include Stories**: Generate the 9 named personas
   - **With Plans**: Percentage of cases with intervention plans
   - **With Visits**: Percentage of cases with home visits
   - **With Notes**: Percentage of cases with progress notes
   - **Closed %**: Percentage of cases to close
3. Click **Generate Cases**
4. View generated cases in the Case Management list

### Recommended Demo Order

For comprehensive cross-module demos:

1. Run `spp_demo` story generation (creates registrants)
2. Run `spp_mis_demo_v2` (creates programs and enrollments)
3. Run `spp_grm_demo` (creates GRM tickets)
4. Run `spp_case_demo` (creates cases with cross-references)

### Programmatic Usage

```python
generator = env['spp.case.demo.generator'].create({
    'name': 'Case Demo',
    'number_of_cases': 25,
    'days_back': 120,
    'include_stories': True,
    'percentage_with_plans': 70,
    'percentage_with_visits': 60,
    'percentage_with_notes': 80,
    'percentage_closed': 40,
    'link_to_beneficiaries': True,
})
action = generator.generate_cases()
```

## Demo Points by Story

### Maria Santos - Full Case Lifecycle

- Complete case from intake to successful closure
- Intervention plan with multiple activities
- Home visits with documentation
- Progress notes showing improvement
- Program graduation success

### Juan Dela Cruz - Emergency Response

- High intensity (Level 3) urgent case
- Same-day emergency assessment
- Multiple rapid interventions
- Escalated from GRM ticket
- Emergency shelter and cash assistance

### David Martinez - Disability Support

- Disability-focused case management
- Integration with Disability Support Grant
- Medical equipment coordination
- Inclusive education advocacy
- Multi-service referral workflow

### Fatima Al-Rahman - GRM Escalation

- GRM to case management escalation
- Program enrollment assistance
- Universal Child Grant integration
- Quick resolution pathway
- Proactive outreach from inquiry

## Technical Details

### Models

- `spp.case.demo.generator` - Core generator logic
- `spp.case.demo.wizard` - Wizard interface

### Key Files

- `models/case_demo_stories.py` - Story definitions
- `models/generate_cases.py` - Generator implementation
- `data/case_types.xml` - Case type definitions
- `data/case_stages.xml` - Case stage definitions

## License

LGPL-3

## Credits

**Authors**: OpenSPP.org

**Maintainers**: jeremi, gonzalesedwin1123
