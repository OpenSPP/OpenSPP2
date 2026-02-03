Generic alert engine for threshold monitoring, expiry tracking, and deadline management. Provides base models and state machine for alert lifecycle tracking. Consumer modules (like `spp_drims`) extend these models and implement evaluation logic to generate alerts based on domain-specific conditions.

### Key Capabilities

- Track alert lifecycle through state machine: active → acknowledged → resolved
- Record resolution details including user, timestamp, and notes
- Classify alerts by type using `spp.vocabulary` codes (threshold, expiry, deadline, manual, system)
- Prioritize alerts as low, medium, high, or critical
- Send mail notifications via `mail.thread` integration
- Auto-generate alert references in ALR-YYYY-NNNNN format

### Key Models

| Model              | Description                                             |
| ------------------ | ------------------------------------------------------- |
| `spp.alert`        | Alert instance with state tracking and resolution workflow |
| `spp.alert.rule`   | Rule configuration for monitoring criteria and thresholds  |

### Configuration

After installing:

1. Navigate to **Settings > Technical > Alerts > Alert Rules**
2. Create rules specifying alert type, priority, threshold values, and days before deadline
3. Consumer modules implement checking logic (e.g., cron jobs or event handlers) to evaluate rules and create alerts

### UI Location

- **Menu**: Settings > Technical > Alerts > Alerts
- **Configuration**: Settings > Technical > Alerts > Alert Rules
- **Form Tabs**: Details, Resolution (alerts); Thresholds (rules)

### Security

| Group                            | Access                             |
| -------------------------------- | ---------------------------------- |
| `spp_alerts.group_alerts_viewer` | Read alerts                        |
| `spp_alerts.group_alerts_officer` | Read/Write/Create (no delete) alerts |
| `spp_alerts.group_alerts_manager` | Full CRUD on alerts and rules      |

### Extension Points

- Inherit `spp.alert` to add domain-specific fields (e.g., stock levels, document references)
- Inherit `spp.alert.rule` to add custom threshold or evaluation criteria
- Override `action_acknowledge()` or `action_resolve()` to add custom workflow steps
- Consumer modules implement alert checking via cron jobs or event handlers that evaluate rules and call `create()` on `spp.alert`

### Dependencies

`base`, `mail`, `spp_security`, `spp_vocabulary`
