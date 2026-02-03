Demo data generator for SP-MIS programs. Creates 6 social protection programs with CEL eligibility expressions, enrolls 8 demo personas with payment histories, and optionally generates volume data for testing. Activates registry variables from `spp_studio` and installs Logic Packs for eligibility rules.

### Key Capabilities

- Generate 6 programs (Child Grant, Elderly Pension, Emergency Relief, Cash Transfer, Disability Support, Food Assistance) with CEL expressions
- Enroll 8 demo personas with predefined stories and payment histories covering all demo scenarios
- Install Logic Packs from `spp_studio` for eligibility rules (child_benefit, social_pension, vulnerability_assessment, cash_transfer_basic, disability_assistance)
- Activate registry variables (age, child_count, hh_total_income, dependency_ratio, etc.) via post_init_hook
- Generate volume data with configurable random enrollments for dashboard testing
- Create change requests at various workflow stages (draft, pending, approved, rejected)
- Cross-module integration: automatically creates GRM tickets and case records when those modules are installed

### Key Models

| Model                    | Description                                     |
| ------------------------ | ----------------------------------------------- |
| `spp.mis.demo.generator` | Core demo generator with all generation logic   |
| `spp.mis.demo.wizard`    | Wizard interface (inherits from generator)      |

### Configuration

After installing:

1. Navigate to **Settings > Demo Data > Load MIS Demo**
2. The wizard opens with options for demo mode (Sales, Training, Testing, Complete)
3. Click "Load Demo Data" to generate

For automatic generation on install:

```bash
ODOO_INIT_MODULES=spp_mis_demo_v2 docker compose --profile ui up -d
```

For programmatic generation:

```python
generator = env['spp.mis.demo.wizard'].create({'name': 'Demo'})
generator.action_generate_demo_data()
```

### Demo Programs

All programs use CEL expressions with activated registry variables:

- **Universal Child Grant**: `r.is_group == true and child_count > 0` (member aggregation)
- **Elderly Social Pension**: `r.is_group == false and age >= retirement_age` (age computation)
- **Emergency Relief Fund**: `dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0)` (compound conditions)
- **Cash Transfer Program**: `hh_total_income < poverty_line and hh_size >= 2` (income-based targeting)
- **Disability Support Grant**: `r.is_group == true and has_disabled_member` (member existence check)
- **Food Assistance**: `r.is_registrant == true and r.active == true` (simple field comparison)

### UI Location

- **Menu**: Settings > Demo Data > Load MIS Demo
- **Form**: Wizard with generation options (demo mode, Logic Pack installation, volume data configuration)

### Security

| Group                          | Access    |
| ------------------------------ | --------- |
| `spp_security.group_spp_admin` | Full CRUD |

### Extension Points

- Override `_create_demo_programs()` to customize program definitions
- Override `_enroll_demo_stories()` to modify enrollment logic
- Add custom demo modes by extending `demo_mode` selection field
- Inherit `spp.mis.demo.generator` to add fields or generation methods

### Dependencies

`spp_starter_sp_mis`, `spp_cr_types_advanced`, `spp_demo`, `spp_gis_report`, `spp_claim_169`
