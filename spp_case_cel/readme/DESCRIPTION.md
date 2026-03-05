Automated case triage and assignment using CEL (Common Expression Language) rules. Evaluates conditions on case creation to automatically set case properties (intensity, priority, type, risk factors) and assign cases to workers or teams based on workload balancing.

### Key Capabilities

- Define triage rules that automatically categorize cases by intensity level, priority, and type based on CEL conditions
- Add risk factors and vulnerabilities automatically when triage rules match
- Define assignment rules that route cases to specific teams, workers, or supervisors
- Balance workload by assigning to team members with lowest active caseload
- Track rule effectiveness with match counters
- Evaluate rules in sequence order with first-match wins

### Key Models

| Model                         | Description                                                      |
| ----------------------------- | ---------------------------------------------------------------- |
| `spp.case.triage.rule`        | CEL-based rule for automatic case categorization and risk tagging |
| `spp.case.assignment.rule`    | CEL-based rule for automatic case assignment with workload balancing |
| `spp.case`                    | Extended to apply triage and assignment rules on creation        |

### Configuration

After installing:

1. Navigate to **Case Management > Configuration > CEL Rules > Triage Rules**
2. Create triage rules with CEL conditions and actions (set intensity, priority, case type, risk factors)
3. Navigate to **Case Management > Configuration > CEL Rules > Assignment Rules**
4. Create assignment rules with team/worker assignments and workload balancing settings

### UI Location

- **Triage Rules**: Case Management > Configuration > CEL Rules > Triage Rules
- **Assignment Rules**: Case Management > Configuration > CEL Rules > Assignment Rules
- **Form Tabs (Triage)**: Condition, Actions
- **Form Tabs (Assignment)**: Condition, Assignment

### Security

| Group                            | Access    |
| -------------------------------- | --------- |
| `spp_case_base.group_case_worker` | Read      |
| `spp_case_base.group_case_manager` | Full CRUD |

### Extension Points

- Override `spp.case.triage.rule._build_evaluation_context()` to add custom variables for triage conditions
- Override `spp.case.assignment.rule._build_evaluation_context()` to add custom variables for assignment conditions
- Override `spp.case.assignment.rule._get_worker_with_lowest_caseload()` to customize workload calculation

### Dependencies

`spp_security`, `spp_case_base`, `spp_cel_domain`
