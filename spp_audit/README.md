# OpenSPP Audit Module

Comprehensive audit trail system for OpenSPP that tracks all data modifications and user
actions across the platform. Supports multiple backends with tamper-resistant
configuration.

## Features

- **Automatic Logging**: Tracks create, write, and unlink operations on configured
  models
- **Lifecycle Actions**: Explicit logging for state transitions (enroll, approve,
  reject, etc.)
- **Multiple Backends**: Database, file (JSONL), syslog, and HTTP endpoints
- **Tamper-Resistant Config**: Configuration priority prevents database-level tampering
- **Self-Protection**: Audit rule changes are logged to non-DB backends
- **Optional Chatter Integration**: Post audit summaries to record's mail.thread

## Quick Start

1. Install the module
2. Go to **Settings > Technical > Audit > Audit Rules**
3. Configure which models and actions to audit
4. Optionally enable additional backends (file, syslog, HTTP)

## Configuration

Configuration uses a priority system (highest to lowest):

1. **Environment Variables** (cannot be overridden)
2. **Config File** (`odoo.conf`)
3. **Database** (`ir.config_parameter`)

### Environment Variables

```bash
# Enable/disable backends
export OPENSPP_AUDIT_BACKEND_DB=true
export OPENSPP_AUDIT_BACKEND_FILE=true
export OPENSPP_AUDIT_BACKEND_SYSLOG=false
export OPENSPP_AUDIT_BACKEND_HTTP=false

# File backend settings
export OPENSPP_AUDIT_FILE_PATH=/var/log/openspp/audit.jsonl

# HTTP backend settings
export OPENSPP_AUDIT_HTTP_URL=https://siem.example.com/ingest
export OPENSPP_AUDIT_HTTP_AUTH_HEADER="Bearer your-token-here"

# Syslog settings
export OPENSPP_AUDIT_SYSLOG_HOST=localhost
export OPENSPP_AUDIT_SYSLOG_PORT=514

# Mandatory models (comma-separated, empty by default)
export OPENSPP_AUDIT_MANDATORY_MODELS=res.partner,spp.program
```

### Config File (odoo.conf)

```ini
[options]
# Enable/disable backends
spp_audit_backend_db = true
spp_audit_backend_file = true
spp_audit_backend_syslog = false
spp_audit_backend_http = false

# File backend
spp_audit_file_path = /var/log/openspp/audit.jsonl

# HTTP backend
spp_audit_http_url = https://siem.example.com/ingest
spp_audit_http_auth_header = Bearer your-token-here

# Syslog backend
spp_audit_syslog_host = localhost
spp_audit_syslog_port = 514

# Mandatory models (empty by default)
spp_audit_mandatory_models =
```

### Database Parameters

Set via **Settings > Technical > Parameters > System Parameters**:

| Key                          | Description                | Default                        |
| ---------------------------- | -------------------------- | ------------------------------ |
| `spp_audit.backend_db`       | Enable database backend    | `true`                         |
| `spp_audit.backend_file`     | Enable file backend        | `false`                        |
| `spp_audit.backend_syslog`   | Enable syslog backend      | `false`                        |
| `spp_audit.backend_http`     | Enable HTTP backend        | `false`                        |
| `spp_audit.file_path`        | Path to JSONL audit file   | `/var/log/openspp/audit.jsonl` |
| `spp_audit.http_url`         | HTTP endpoint URL          | (none)                         |
| `spp_audit.http_auth_header` | Authorization header value | (none)                         |

**Note**: Database parameters can be overridden by config file or environment variables.
This prevents a compromised database from disabling audit logging.

## Backends

### Database Backend (default)

Stores audit logs in the `spp.audit.log` model. Logs are viewable in the Odoo UI under
**Settings > Technical > Audit > Audit Logs**.

### File Backend

Writes audit entries as JSON Lines (JSONL) to a file. Each line is a complete JSON
object.

**File Rotation**: Files rotate daily with timestamp suffix (e.g.,
`audit.jsonl.2024-01-15`).

**Example JSONL output**:

```json
{"seq": 1, "ts": "2024-01-15T10:30:45.123456+00:00", "node": "odoo-web-1", "model": "res.partner", "res_id": 42, "method": "write", "user_id": 2, "user_login": "admin", "old_values": {"name": "Old Name"}, "new_values": {"name": "New Name"}}
{"seq": 2, "ts": "2024-01-15T10:31:12.789012+00:00", "node": "odoo-web-1", "model": "spp.program.membership", "res_id": 15, "action": "enroll", "user_id": 5, "user_login": "social_worker"}
```

**Entry Fields**:

- `seq`: Sequence number for gap detection
- `ts`: ISO 8601 timestamp with timezone
- `node`: Node identifier (hostname or container ID)
- `model`: Odoo model name
- `res_id`: Record ID
- `method`: Operation type (create, write, unlink) or `action` for lifecycle events
- `user_id`: User who performed the action
- `user_login`: Username
- `old_values`/`new_values`: Changed field values (for write operations)

### Syslog Backend

Sends audit entries to a syslog server. Useful for centralized logging infrastructure.

```ini
spp_audit_backend_syslog = true
spp_audit_syslog_host = syslog.example.com
spp_audit_syslog_port = 514
```

### HTTP Backend

POSTs audit entries as JSON to an HTTP endpoint. Useful for SIEM integration.

```ini
spp_audit_backend_http = true
spp_audit_http_url = https://siem.example.com/api/v1/ingest
spp_audit_http_auth_header = Bearer your-api-token
```

The HTTP backend sends a POST request with:

- `Content-Type: application/json`
- `Authorization: <your auth header>` (if configured)
- Body: JSON audit entry

## Audit Rules

### Automatic Logging

Configure which models and operations to audit:

| Field                 | Description                                   |
| --------------------- | --------------------------------------------- |
| **Model**             | The Odoo model to audit                       |
| **Log Create**        | Audit record creation                         |
| **Log Write**         | Audit record modifications                    |
| **Log Unlink**        | Audit record deletion                         |
| **Subscribed Fields** | Specific fields to track (empty = all fields) |

### Lifecycle Actions

Enable explicit action logging for state transitions:

| Field           | Description              |
| --------------- | ------------------------ |
| **Log Enroll**  | Enrollment into programs |
| **Log Pause**   | Pausing memberships      |
| **Log Unpause** | Resuming memberships     |
| **Log Exit**    | Exiting from programs    |
| **Log Approve** | Approval actions         |
| **Log Reject**  | Rejection actions        |
| **Log Submit**  | Submission actions       |

### File Access Logging

| Field            | Description          |
| ---------------- | -------------------- |
| **Log Upload**   | File upload events   |
| **Log Download** | File download events |
| **Log Preview**  | File preview events  |

### Chatter Integration

Enable **Post to Chatter** to post audit summaries to the record's mail.thread. This is
disabled by default and should only be enabled for low-volume, human-reviewed records.

## API Usage

### Logging Lifecycle Actions

From your code, call `log_lifecycle_action()` to record explicit actions:

```python
# Get the audit rule for your model
rule = self.env["spp.audit.rule"].search([
    ("model_id.model", "=", "spp.program.membership")
], limit=1)

# Log a lifecycle action
if rule:
    rule.log_lifecycle_action(
        action="enroll",
        records=membership_records,
        extra_data={"program_id": program.id}
    )
```

### Using the Audit Decorator

For custom methods that should be audited:

```python
from odoo.addons.spp_audit.tools.decorator import audit

class MyModel(models.Model):
    _name = "my.model"

    @audit
    def my_audited_method(self):
        # This method's execution will be logged
        pass
```

## Security Considerations

### Tamper-Resistant Configuration

The configuration priority system ensures that:

1. Environment variables cannot be overridden by any other source
2. Config file settings cannot be overridden by database parameters
3. A compromised database cannot disable audit logging

**Recommendation**: Set critical audit settings in environment variables or config file,
not in the database.

### Self-Protection

Changes to audit rules (create, write, unlink on `spp.audit.rule`) are automatically
logged to all enabled non-database backends. This ensures that attempts to disable
auditing are themselves audited to external systems.

### Access Control

The module defines these security groups:

- **Audit Manager** (`spp_audit.group_manager`): Full access to audit rules and logs
- **Audit User**: Read-only access to audit logs

## Sequence Numbers and Gap Detection

Each audit entry includes:

- `seq`: Auto-incrementing sequence number
- `ts`: Timestamp
- `node`: Node identifier

Use the tuple `(node, ts, seq)` to detect gaps in audit logs. Gaps may indicate:

- System restarts
- Log tampering
- Network issues (for remote backends)

**Note**: In multi-process deployments, sequence numbers are per-process. Use the node
identifier to correlate sequences.

## Troubleshooting

### File Backend Not Writing

1. Check file path permissions
2. Verify the directory exists
3. Check Odoo logs for write errors

### HTTP Backend Failing

1. Verify the URL is accessible
2. Check authentication header format
3. Review Odoo logs for HTTP errors (logged as warnings)

### Missing Audit Logs

1. Verify the audit rule is active
2. Check that the model and actions are configured
3. Ensure the backend is enabled in configuration

## Version History

- **19.0.1.4.0**: Added pluggable backend system (file, syslog, HTTP)
- **19.0.1.3.0**: Consolidated from spp_audit_log, spp_audit_post, spp_audit_config
