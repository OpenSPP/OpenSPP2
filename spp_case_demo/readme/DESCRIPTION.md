Demo data generator for Case Management system. Creates realistic cases with intervention plans, home visits, progress notes, and service referrals. Includes 9 fixed demo stories for training and sales demos, plus configurable random case generation for volume testing.

### Key Capabilities

- Generate 9 fixed demo stories with predictable personas and case progressions for consistent training scenarios
- Create random volume cases with configurable distribution percentages for plans, visits, notes, and closures
- Link generated cases to existing registrants or create standalone cases
- Backdate case records and related activities to simulate realistic timelines over configurable day ranges
- Create intervention plans with multiple interventions across case lifecycle stages
- Generate home visits, office visits, phone calls, and virtual visits with contextual notes
- Install default case types (General Support, Emergency Assistance, Child Protection, Health Support, Livelihood Development, Housing Assistance) and case stages (Intake, Assessment, Planning, Implementation, Monitoring, Closure)

### Key Models

| Model                     | Description                                                |
| ------------------------- | ---------------------------------------------------------- |
| `spp.case.demo.generator` | Core logic for configuring and generating demo data       |
| `spp.case.demo.wizard`    | Wizard interface for demo data generation (inherits generator) |

### Configuration

After installing:

1. Navigate to **Case Management > Configuration > Generate Demo Data**
2. Configure generation parameters:
   - Number of cases to generate (1-5,000)
   - Days back to distribute cases over
   - Enable "Include Demo Stories" to create 9 fixed personas
   - Set distribution percentages for plans, visits, notes, and closed cases
   - Choose locale origin for Faker data generation
   - Select whether to link cases to existing beneficiaries
3. Click "Generate Cases" to create demo data
4. View generated cases in Case Management > Cases (filtered by generated IDs)

### UI Location

- **Menu**: Case Management > Configuration > Generate Demo Data
- **Generated Cases**: View results in Case Management > Cases

### Security

| Group             | Access    |
| ----------------- | --------- |
| `base.group_user` | Full CRUD |

### Demo Stories

When "Include Demo Stories" is enabled, generates 9 fixed personas:

- **Santos Family Support**: Complete case lifecycle from intake to successful closure
- **Dela Cruz Emergency Response**: High intensity urgent case with same-day response
- **Garcia Elder Care Coordination**: Long-term care case with service referrals
- **Mendoza Child Welfare**: Child protection case with safety assessments and frequent visits
- **Hassan Resettlement Support**: Displaced person case escalated from GRM
- **Morales Household Crisis**: Multi-member household identified during outreach
- **Martinez Disability Support**: Disability-focused case with equipment and education services
- **Al-Rahman Family Assessment**: GRM-initiated assessment leading to program enrollment
- **Said Family Support**: Pattern detection from repeat GRM tickets

### Dependencies

`spp_demo`, `spp_case_base`, `spp_security`, `faker` (Python)
