Case management system for social protection programs. Tracks cases from intake through assessment, intervention planning, and closure with workflow stages, risk assessments, and team assignment. Automated review scheduling via cron job ensures timely case monitoring.

### Key Capabilities

- Track cases for individuals, households, or groups with configurable types and workflow stages
- Conduct assessments with risk scoring (0-100) and automatic risk level classification (low/medium/high/critical)
- Create versioned intervention plans with approval workflows and progress tracking
- Document case activities: visits, notes, referrals to external services
- Assign cases to workers and teams with supervisor oversight
- Schedule automated review reminders for cases approaching or past review dates

### Key Models

| Model                        | Description                                     |
| ---------------------------- | ----------------------------------------------- |
| `spp.case`                   | Core case record with client and assignment    |
| `spp.case.type`              | Case type with default intensity and caseload   |
| `spp.case.stage`             | Workflow stage with phase and requirements      |
| `spp.case.assessment`        | Assessment with risk score and findings         |
| `spp.case.intervention.plan` | Versioned plan with approval workflow           |
| `spp.case.intervention`      | Individual intervention with status tracking    |
| `spp.case.visit`             | Client visit with type and notes                |
| `spp.case.note`              | Case note with confidentiality flag             |
| `spp.case.referral`          | External service referral with status           |
| `spp.case.team`              | Team with supervisor and members                |
| `spp.case.risk.factor`       | Risk factor with severity weight                |
| `spp.case.vulnerability`     | Vulnerability for assessment                    |
| `spp.case.closure.reason`    | Closure reason with outcome type                |

### Configuration

After installing:

1. Navigate to **Case Management > Configuration > Case Setup > Case Types** and create case types
2. Navigate to **Case Management > Configuration > Case Setup > Case Stages** and define workflow stages
3. Navigate to **Case Management > Configuration > Case Setup > Case Teams** and create teams
4. Navigate to **Case Management > Configuration > Assessment > Risk Factors** and define risk factors
5. Navigate to **Case Management > Configuration > Assessment > Vulnerabilities** and define vulnerabilities
6. Navigate to **Case Management > Configuration > Closure > Closure Reasons** and set up closure reasons
7. Verify the cron job **Case Management: Check Review Schedules** is active under **Settings > Technical > Scheduled Actions**

### UI Location

- **Cases**: Case Management > Cases > All Cases / My Cases / Unassigned Cases
- **Activities**: Case Management > Activities > Visits / Notes / Referrals / Assessments
- **Planning**: Case Management > Planning > Intervention Plans / Interventions
- **Configuration**: Case Management > Configuration (Manager role required)
- **Form tabs**: Details, Participants, Programs, History

### Security

| Group                           | Access                                          |
| ------------------------------- | ----------------------------------------------- |
| `group_case_viewer`             | Read-only access to all case records           |
| `group_case_worker`             | Full CRUD on cases and activities               |
| `group_case_supervisor`         | Full CRUD on cases and activities, read config  |
| `group_case_manager`            | Full CRUD including configuration               |

### Extension Points

- Override `_check_stage_requirements()` on `spp.case` for custom stage validation
- Override `_compute_risk_level()` on `spp.case.assessment` to customize risk calculation thresholds
- Extend `spp.case.intervention.plan` with domain-specific fields
- Hook `_cron_check_reviews()` to add custom review logic or notification templates

### Dependencies

`base`, `mail`, `portal`, `spp_security`
