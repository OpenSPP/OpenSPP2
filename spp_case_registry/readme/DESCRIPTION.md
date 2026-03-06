Integrates case management with the registry system by linking cases to individual registrants and households. Automatically detects previous cases for the same registrant or household, tracks household member involvement, and associates cases with geographic areas. Auto-installs when both `spp_case_base` and `spp_registry` are present.

### Key Capabilities

- Link cases to individual registrants or household groups from the registry
- Automatically populate case details from registrant profiles (household membership, geographic area)
- Detect and display previous cases for the same registrant or household
- Track which household members are involved in each case
- View all cases from a registrant or household profile via smart button
- Filter and group cases by registrant, household, or geographic area

### Key Models

| Model         | Description                                                                      |
| ------------- | -------------------------------------------------------------------------------- |
| `spp.case`    | Extended with registrant_id, household_id, area_id, and previous case detection |
| `res.partner` | Extended with case counts and relationships to cases as registrant or household  |

### Configuration

No configuration required. The module auto-installs when both case management and registry modules are present.

### UI Location

- **Menu**: Case Management > Cases > All Cases (fields added to existing case forms and tree views)
- **Registrant Profile**: Smart button showing active/total case count, "Cases" tab listing all related cases
- **Case Form**: Registrant, Household, and Area fields in header; "Household Members" tab when applicable

### Security

| Group                              | Access                        |
| ---------------------------------- | ----------------------------- |
| `spp_case_base.group_case_officer` | Read/Write/Create (no delete) |
| `spp_case_base.group_case_manager` | Full CRUD                     |

### Extension Points

- Override `_onchange_registrant_id()` to customize auto-fill logic when registrant is selected
- Override `_compute_previous_cases()` to modify previous case detection rules
- Inherit `spp.case` to add additional registry-related fields or constraints

### Dependencies

`spp_security`, `spp_case_base`, `spp_registry`, `spp_area`
