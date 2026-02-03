Tracks all data modifications and user actions across OpenSPP models by logging create, write, and unlink operations. Records old and new field values for configured models and dispatches audit entries to multiple backends (database, file, syslog, HTTP) simultaneously. Supports tamper-resistant configuration where environment variables and config files override database settings, ensuring audit logging cannot be disabled through compromised database access.

### Key Capabilities

- **Automatic Operation Logging**: Intercepts create, write, and unlink operations on configured models via method decoration
- **Lifecycle Action Logging**: Explicitly logs state transitions like activate, deactivate, approve, reject through `log_lifecycle_action()` API
- **File Access Tracking**: Records download, preview, and export actions when enabled for specific models
- **Multi-Backend Dispatch**: Writes to database (UI-visible), JSONL files (daily rotation), syslog, and HTTP endpoints concurrently
- **Tamper-Resistant Config**: Environment variables and `odoo.conf` override database parameters to prevent audit disabling
- **Self-Protection**: Logs changes to `spp.audit.rule` records directly to non-database backends
- **Optional Chatter Integration**: Posts audit summaries to record's mail.thread when explicitly enabled

### Key Models

| Model            | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `spp.audit.rule` | Defines which models and operations to audit, with field filters |
| `spp.audit.log`  | Database-stored audit entries with old/new value comparison      |

### Configuration

After installing:

1. Navigate to **Audit Log > Audit > Rule**
2. Create or modify audit rules specifying model, operations (create/write/unlink), and fields to track
3. Enable additional backends via environment variables or `odoo.conf`:
   - `OPENSPP_AUDIT_BACKEND_FILE=true` / `spp_audit_backend_file = true`
   - `OPENSPP_AUDIT_BACKEND_SYSLOG=true` / `spp_audit_backend_syslog = true`
   - `OPENSPP_AUDIT_BACKEND_HTTP=true` / `spp_audit_backend_http = true`
4. Configure backend-specific settings (file path, HTTP endpoint, syslog host)

### UI Location

- **Menu**: Audit Log > Audit > Rule (configure audit rules)
- **Menu**: Audit Log > Audit > Log (view database-stored audit entries)
- **Action**: "View logs" action menu appears on audited model forms when `is_view_logs` enabled

**Tabs (Audit Log form)**:

- **Changes**: Displays old/new field values in table format

**Tabs (Audit Rule form)**:

- **Related Rules**: Shows child rules when parent model inherits mail.thread

### Security

| Group                           | Access                                         |
| ------------------------------- | ---------------------------------------------- |
| `spp_audit.group_audit_manager` | Full CRUD on audit rules and logs              |
| `spp_security.group_spp_admin`  | Includes audit manager privileges (via imply)  |

Audit logs cannot be deleted by default (`ALLOW_DELETE = False` in code, despite `perm_unlink=1` in access rules).

### Extension Points

- Call `log_lifecycle_action(model_name, record_id, action, old_values, new_values)` to explicitly log state transitions
- Inherit `spp.audit.backend` and register new backend types via `AuditBackendRegistry.register_backend()`
- Override `_format_data_to_log()` to customize field value sanitization
- Extend `spp.audit.rule` with additional logging flags for domain-specific actions

### Dependencies

`base`, `mail`, `spp_registry`, `spp_security`, `spp_programs`, `spp_service_points`

External Python: `requests` (HTTP backend)
