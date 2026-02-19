# OpenSPP MIS Demo V2

## Overview

This module provides Demo Generator V2 for SP-MIS programs, following the simplified
"Fixed Stories + Volume" architecture. It creates predictable demo data that integrates
with the demo stories from `spp_demo` and showcases CEL expressions with Logic Packs
from `spp_studio`.

## Features

- **Demo Programs**: 6 programs with CEL eligibility expressions
- **Logic Pack Integration**: Programs link to reusable Logic Packs
- **CEL Expression Showcase**: Demonstrates member queries, metrics, and constants
- **Story Enrollments**: 9 demo personas with memorable names
- **Change Requests**: All 11 CR types with approval workflows
- **Multi-Mode Wizard**: Sales, Training, Testing, and Complete modes

## Demo Programs

The 6 demo programs showcase different CEL expression patterns using **activated
registry variables**:

| Program                  | Target     | CEL Pattern                                   | Logic Pack               |
| ------------------------ | ---------- | --------------------------------------------- | ------------------------ |
| Universal Child Grant    | Group      | `child_count > 0` (variable)                  | child_benefit            |
| Elderly Social Pension   | Individual | `age >= retirement_age` (computed + constant) | social_pension           |
| Emergency Relief Fund    | Group      | `dependency_ratio >= 1.5` (computed variable) | vulnerability_assessment |
| Cash Transfer Program    | Group      | `hh_total_income < poverty_line` (aggregate)  | cash_transfer_basic      |
| Disability Support Grant | Group      | `has_disabled_member` (computed variable)     | disability_assistance    |
| Food Assistance          | Individual | `r.active == true` (simple field)             | None (inline CEL)        |

## Demo Stories (12 Personas)

### Primary Stories - Eligible

| Persona          | MIS Program              | GRM Ticket                | Case Story               |
| ---------------- | ------------------------ | ------------------------- | ------------------------ |
| Maria Santos     | Cash Transfer Program    | Graduation inquiry        | Santos Family Support    |
| Juan Dela Cruz   | Cash Transfer Program    | Payment not received      | Dela Cruz Emergency      |
| Rosa Garcia      | Elderly Pension + Food   | Delivery schedule inquiry | Garcia Elder Care        |
| Carlos Morales   | Universal Child Grant    | Adding new child          | Morales Household Crisis |
| Ibrahim Hassan   | Emergency Relief Fund    | Resettlement support      | Hassan Resettlement      |
| David Martinez   | Disability Support Grant | Grant application status  | Martinez Disability      |
| Fatima Al-Rahman | Universal Child Grant    | Eligibility inquiry       | Al-Rahman Assessment     |
| Ahmed Said       | Cash Transfer Program    | Multiple tickets (3)      | Said Family Support      |

### Rejection Demonstrations - Ineligible

| Persona               | Program Applied For    | Rejection Reason          |
| --------------------- | ---------------------- | ------------------------- |
| Mary Johnson          | Elderly Social Pension | Below retirement age (55) |
| Childless Household   | Universal Child Grant  | No children under 18      |
| High Income Household | Cash Transfer Program  | Income above poverty line |

## CEL Expression Examples

These expressions use **activated registry variables** for cleaner, more maintainable
eligibility rules.

### Universal Child Grant

```cel
r.is_group == true and child_count > 0
```

Uses the `child_count` aggregate variable (automatically counts members under 18).

### Elderly Social Pension

```cel
r.is_group == false and age >= retirement_age
```

Uses the `age` computed variable and `retirement_age` constant (default: 60).

### Emergency Relief Fund

```cel
r.is_group == true and (dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0))
```

Uses `dependency_ratio`, `is_female_headed`, and `elderly_count` variables for
vulnerability targeting.

### Cash Transfer Program

```cel
r.is_group == true and hh_total_income < poverty_line and hh_size >= 2
```

Uses `hh_total_income` aggregate, `poverty_line` constant, and `hh_size` aggregate.

### Disability Support Grant

```cel
r.is_group == true and has_disabled_member
```

Uses the `has_disabled_member` computed variable (checks `is_person_with_disability` on
members).

## Cross-Module Integration

### Integrated Demo Ecosystem

MIS Demo V2 is designed to work seamlessly with GRM and Case Management demos:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  spp_mis_demo_v2│     │  spp_grm_demo   │     │  spp_case_demo  │
│                 │     │                 │     │                 │
│  • Programs     │────▶│  • Tickets      │────▶│  • Cases        │
│  • Enrollments  │     │  • Escalations  │     │  • Interventions│
│  • Payments     │     │  • Resolutions  │     │  • Plans        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                    Shared Personas (8 beneficiaries)
```

### Automatic Cross-Module Generation

The MIS Demo wizard can automatically generate GRM tickets and Cases when those modules
are installed. Simply enable the options in the wizard:

- **Generate GRM Demo**: Creates story-based tickets + volume tickets (requires
  `spp_grm_demo`)
- **Generate Case Demo**: Creates story-based cases + volume cases (requires
  `spp_case_demo`)

This eliminates the need to run separate wizards for each module.

### Manual Demo Order (Alternative)

If you prefer to run demos separately:

1. **spp_demo** - Creates base registrants with persona names
2. **spp_mis_demo_v2** - Creates programs and enrolls personas
3. **spp_grm_demo** - Creates tickets referencing program issues
4. **spp_case_demo** - Creates cases escalated from GRM

### Demo Scenario: Juan Dela Cruz Journey

1. **MIS**: Enrolled in Cash Transfer Program, receiving $150/month
2. **GRM**: Files ticket "Payment not received after house fire"
3. **GRM**: Ticket escalated due to emergency situation
4. **Case**: Emergency case opened with shelter and cash assistance interventions
5. **Case**: Family stabilized, case moves to monitoring phase

### Demo Scenario: David Martinez Journey

1. **MIS**: Applies for Disability Support Grant for son Miguel
2. **GRM**: Files ticket asking about application status
3. **GRM**: Referred to case management for comprehensive support
4. **Case**: Case opened for equipment assistance and education enrollment
5. **MIS**: Grant approved - $175/month (base $100 + $75 per disabled member)

## Dependencies

- `spp_demo` - Demo story infrastructure
- `spp_programs` - Program management
- `spp_registry` - Registry module
- `spp_cel_domain` - CEL variable system (ADR-008, ADR-017)
- `spp_studio` - Logic Packs and expressions
- `spp_change_request_v2` - Change request workflows
- Optional: `spp_grm_demo` - For cross-module GRM integration
- Optional: `spp_case_demo` - For cross-module case integration

## Installation

1. Install the module through Odoo Apps menu
2. Ensure `spp_demo` is installed with stories generated

## Usage

### Using the Wizard

1. Navigate to **Programs > Generate MIS Demo Data**
2. Select **Demo Mode**:
   - **Sales Demo**: Fixed stories, minimal data, fast
   - **Partner Training**: Full programs, Logic Packs, comprehensive
   - **Developer Testing**: Volume data, random generation, scale testing
   - **Complete Demo**: All features enabled
3. Configure additional options as needed
4. Click **Generate Demo Data**

### Demo Mode Presets

| Mode     | Stories | Programs | Logic Packs | Volume  | Personas |
| -------- | ------- | -------- | ----------- | ------- | -------- |
| Sales    | Yes     | Yes      | No          | No      | No       |
| Training | Yes     | Yes      | Yes         | Minimal | Yes      |
| Testing  | Yes     | Yes      | No          | High    | No       |
| Complete | Yes     | Yes      | Yes         | Yes     | Yes      |

### Programmatic Usage

```python
# Create and run the generator with training mode
generator = env['spp.mis.demo.wizard'].create({
    'name': 'Training Demo',
    'demo_mode': 'training',
    'install_logic_packs': True,
    'include_test_personas': True,
    'create_demo_programs': True,
    'enroll_demo_stories': True,
})
generator.action_generate_demo_data()
```

## Change Request Integration

The demo creates change requests covering all 11 CR types:

### CR Types Demonstrated

| Type              | Description               | Demo State         |
| ----------------- | ------------------------- | ------------------ |
| edit_individual   | Basic data update         | Approved           |
| update_id         | ID document update        | Approved           |
| exit_registrant   | Registry exit             | Approved + Applied |
| add_member        | Add household member      | Approved           |
| remove_member     | Remove member             | Pending            |
| transfer_member   | Inter-household transfer  | Pending            |
| change_hoh        | Head of household change  | Approved           |
| create_group      | Create new group          | Draft              |
| split_household   | Split into two households | Draft              |
| merge_registrants | Merge duplicates          | Rejected           |

### Workflow States Demonstrated

- **Draft**: New CRs not yet submitted
- **Pending**: Awaiting approval
- **Approved**: Approved (may or may not be applied)
- **Rejected**: Rejected with reason documented
- **Revision**: Sent back for correction

## Logic Pack Integration

Programs link to pre-built Logic Packs from `spp_studio`:

```python
DEMO_LOGIC_PACKS = [
    "child_benefit",         # Universal Child Grant
    "social_pension",        # Elderly Social Pension
    "vulnerability_assessment",  # Emergency Relief
    "cash_transfer_basic",   # Cash Transfer Program
    "disability_assistance", # Disability Support Grant
]
```

### Installing Logic Packs

```python
from odoo.addons.spp_mis_demo_v2.models.demo_variables import install_demo_packs
installed = install_demo_packs(env)
```

## Registry Variables

On module installation, registry variables are **automatically activated** and ready for
use in Logic Studio and program expressions. This includes both standard variables from
`spp_studio` and demo-specific variables.

### Standard Variables (from spp_studio)

| Category                      | Variables                                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Demographics**              | `age`                                                                                                     |
| **Household Composition**     | `hh_size`, `child_count`, `elderly_count`, `working_age_count`                                            |
| **Household Characteristics** | `is_female_headed`, `is_elderly_headed`, `has_disabled_member`, `has_pregnant_member`, `dependency_ratio` |
| **Economic**                  | `per_capita_income`, `hh_total_income`, `hh_avg_income`                                                   |
| **Constants**                 | `poverty_line`, `retirement_age`, `child_age_limit`, `per_child_benefit`, `base_benefit`                  |

### Demo-Specific Variables

| Variable                      | Type      | Default | Description                 |
| ----------------------------- | --------- | ------- | --------------------------- |
| `vulnerability_threshold`     | constant  | 70      | Emergency eligibility score |
| `base_child_grant`            | constant  | 50      | Per-child benefit amount    |
| `disability_grant_base`       | constant  | 100     | Base disability amount      |
| `disability_grant_per_member` | constant  | 75      | Per disabled member bonus   |
| `emergency_tier_1`            | constant  | 500     | Tier 1 emergency amount     |
| `emergency_tier_2`            | constant  | 400     | Tier 2 emergency amount     |
| `emergency_tier_3`            | constant  | 300     | Tier 3 emergency amount     |
| `elderly_pension_amount`      | constant  | 100     | Fixed pension amount        |
| `cash_transfer_amount`        | constant  | 150     | Fixed transfer amount       |
| `disabled_count`              | aggregate | -       | Count of disabled members   |

### Variable Activation

Variables are activated during module installation via `post_init_hook`. The activation:

1. Finds variables by XML ID (e.g., `spp_studio.var_age`)
2. Activates any in `draft` state
3. Skips already active variables
4. Logs results for troubleshooting

```
[spp.mis.demo] Standard variables: 18 activated, 0 already active, 0 errors
[spp.mis.demo] Demo variables: 10 activated, 0 already active, 0 errors
[spp.mis.demo] Registry variables ready: 28 activated, 0 skipped, 0 errors
```

## Technical Details

### Models

- `spp.mis.demo.generator` - Core generator with all logic
- `spp.mis.demo.wizard` - Wizard interface (inherits generator)

### Key Methods

- `action_generate()` - Main entry point
- `_create_demo_programs()` - Creates 6 programs with CEL
- `_enroll_demo_stories()` - Enrolls personas
- `_install_logic_packs()` - Installs required Logic Packs
- `_create_test_personas()` - Creates test personas for Studio
- `_create_change_requests()` - Creates CR demos

### Data Files

- `data/demo_constants.xml` - CEL variable definitions
- `data/demo_personas.xml` - Test personas for Logic Studio
- `data/demo_programs.xml` - Program configurations

## V3 Architecture Alignment

This module follows the V3 Architecture principles:

- **CEL Integration** - All eligibility uses CEL expressions
- **Logic Packs** - Reusable expression bundles
- **Fixed Stories + Volume** - Predictable personas plus random data
- **Multi-Mode** - Different presets for different use cases
- **Change Requests** - Full CR workflow coverage

## License

LGPL-3

## Credits

**Authors**: OpenSPP.org

**Maintainers**: jeremi, gonzalesedwin1123
