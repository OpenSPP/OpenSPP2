Generic alert engine for threshold monitoring, expiry tracking, and deadline
management. Evaluates configurable rules on a daily schedule or on-demand and
generates alerts when conditions are met. Consumer modules (like `spp_drims`)
extend these models to add domain-specific fields.

### Key Capabilities

- Define alert rules with threshold or date conditions against any model
- Evaluate rules via daily cron or "Run Now" button
- Compare numeric fields using 5 operators: <, <=, >, >=, =
- Check date/datetime fields against a days-before window
- Prevent duplicates: skip records with existing active/acknowledged alerts
- Filter monitored records using a visual domain builder
- Track alert lifecycle: active → acknowledged → resolved
- Record resolution details: user, timestamp, and notes
- Navigate from alert to source record via stat button
- Classify alerts by type using `spp.vocabulary` codes
- Prioritize as low, medium, high, or critical
- Auto-generate references in `ALR-YYYY-NNNNN` format

### Key Models

| Model            | Description                                              |
| ---------------- | -------------------------------------------------------- |
| `spp.alert`      | Alert instance with state tracking and resolution audit  |
| `spp.alert.rule` | Rule configuration with evaluation engine and scheduling |

### Configuration

After installing:

1. Navigate to **Settings > Technical > Alerts > Alert Rules**
2. Create rules: select model, rule type (threshold/date), and conditions
3. The daily cron "Alerts: Evaluate Alert Rules" is active by default

### UI Location

- **Menu**: Settings > Technical > Alerts > Alerts
- **Configuration**: Settings > Technical > Alerts > Alert Rules
- **Views**: List, kanban (grouped by state), and form
- **Alert form tabs**: Details, Resolution
- **Rule form**: Description above tabs; Evaluation tab with settings + domain builder

### Security

| Group                             | Alerts                        | Rules     |
| --------------------------------- | ----------------------------- | --------- |
| `spp_alerts.group_alerts_viewer`  | Read                          | Read      |
| `spp_alerts.group_alerts_officer` | Read/Write/Create (no delete) | Read      |
| `spp_alerts.group_alerts_manager` | Full CRUD                     | Full CRUD |

### Extension Points

- Inherit `spp.alert` to add domain-specific fields
- Inherit `spp.alert.rule` to add custom evaluation criteria
- Override `_evaluate_threshold()` or `_evaluate_date()` for custom logic
- Override `action_acknowledge()` or `action_resolve()` for custom workflows
- Rules can be configured via UI without code

### Dependencies

`base`, `mail`, `spp_security`, `spp_vocabulary`
