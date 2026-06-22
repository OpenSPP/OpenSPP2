DCI compliance validation infrastructure for testing DCI protocol implementations. Logs async
callbacks with PII sanitization, provides verification endpoints for compliance tests, and displays
security warnings when insecure DCI configuration options are enabled. Endpoints are disabled by
default and only mount when explicitly enabled for testing.

### Key Capabilities

- Log DCI callbacks with automatic PII sanitization before storage
- Query callback logs via REST API to verify async operations completed
- Wait for specific callbacks with configurable timeout and polling
- Display security warnings when development/testing security settings are enabled
- Automatically cleanup old callback logs via scheduled cron job

### Key Models

| Model                        | Description                                           |
| ---------------------------- | ----------------------------------------------------- |
| `spp.dci.callback.log`       | Stores sanitized callback logs for compliance testing |
| `spp.dci.callback.log.mixin` | Mixin providing context manager for callback logging  |
| `spp.dci.security.warning`   | Abstract model checking for insecure DCI settings     |
| `fastapi.endpoint` (extended)| Adds compliance endpoints to DCI API when enabled     |

### Configuration

After installing:

1. Compliance endpoints are **disabled by default** for production safety
2. Enable for testing via **Settings > Technical > System Parameters**:
   - Set `dci.enable_compliance_endpoints` to `true`
3. Alternatively, endpoints auto-enable when running with `--test-enable`
4. Verify the **DCI: Cleanup Old Callback Logs** scheduled action under
   **Settings > Technical > Scheduled Actions** (runs daily, keeps 7 days of logs)

### UI Location

- **Security Warnings**: Displayed in systray widget when insecure settings detected
- **API Endpoints**: `/dci_api/v1/test/callbacks` (only when enabled)
  - `GET /test/callbacks` - Query callback logs
  - `GET /test/callbacks/stats` - Get callback statistics
  - `POST /test/callbacks/wait` - Wait for specific callback
  - `DELETE /test/callbacks` - Clear callback logs

### Security

| Group               | Access                            |
| ------------------- | --------------------------------- |
| `base.group_system` | Full CRUD on callback logs        |
| `base.group_user`   | Read-only access to callback logs |

**Mount gate pattern**: The `/test/*` compliance endpoints do not exist in the running application
unless explicitly enabled. The `FastAPIEndpointCompliance._get_fastapi_routers()` method checks two
conditions before adding the `verification_router`:

1. `tools.config.get("test_enable")` — Odoo started with the `--test-enable` flag
2. System parameter `dci.enable_compliance_endpoints` set to `"true"`

If neither condition is met, the router is never registered and the endpoints return 404. This means
**no authentication is needed on these endpoints** because they are unreachable in production by
default. When enabled for testing, the endpoints are intentionally open to allow external compliance
test harnesses to interact without credentials.

**Production safety**: Both conditions default to `false`. A standard production deployment never
exposes these endpoints. The `spp.dci.security.warning` model monitors for insecure settings and
displays systray warnings to administrators when testing configuration is active.

### Extension Points

- Inherit `spp.dci.callback.log.mixin` in callback handlers to automatically log callbacks
- Use context manager pattern: `with self.log_dci_callback(...):`
- Override `_sanitize_payload()` to customize PII field detection
- Extend `INSECURE_SETTINGS` list in `spp.dci.security.warning` for additional warnings

### Dependencies

`queue_job`, `spp_dci`, `spp_dci_server`, `spp_dci_server_social`, `spp_registry`, `web`
