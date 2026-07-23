Testing infrastructure for SPDCI protocol compliance validation. Exposes HTTP endpoints that trigger DCI client actions against a mock registry server, allowing external test frameworks to verify that the OpenSPP DCI client implementation conforms to SPDCI specifications. Uses the production `DCIClient` class, ensuring tests validate the actual code path rather than test doubles.

### Key Capabilities

- Trigger DCI search requests via `/dci/test/trigger/search` endpoint
- Trigger subscription operations (subscribe/unsubscribe) via dedicated endpoints
- Query transaction status via `/dci/test/trigger/txn_status` endpoint
- Health check endpoint at `/dci/test/trigger/health` for test framework readiness verification
- Auto-create test data source pointing to mock registry if none exists
- Mark data sources as compliance test fixtures using `is_compliance_test` flag

### Key Models

| Model                 | Description                                      |
| --------------------- | ------------------------------------------------ |
| `spp.dci.data.source` | Extended with `is_compliance_test` boolean field |

### Configuration

After installing:

1. Set system parameter `dci.client_compliance.mock_registry_url` to point to your mock registry (default: `http://mock_registry:3335`)
2. Set system parameter `dci.client_compliance.bearer_token` to a **private** token for authentication. There is no default, and the well-known value `compliance-test-api-key-12345` is rejected; the trigger endpoints refuse to run until a private token is configured.
3. Verify test data source exists under **Settings > Technical > DCI > Configuration > Data Sources** (auto-created if missing)

### Controller Endpoints

| Endpoint                        | Method | Purpose                                   |
| ------------------------------- | ------ | ----------------------------------------- |
| `/dci/test/trigger/search`      | POST   | Trigger async search request              |
| `/dci/test/trigger/subscribe`   | POST   | Trigger subscription request              |
| `/dci/test/trigger/unsubscribe` | POST   | Trigger unsubscription request            |
| `/dci/test/trigger/txn_status`  | POST   | Query transaction status                  |
| `/dci/test/trigger/health`      | GET    | Health check (returns data source config) |

All endpoints use `auth="none"` and `csrf=False` for external test framework access.

### Security

No access control lists. Endpoints are public (`auth="none"`) for test framework integration.

### Extension Points

- Override `_get_test_data_source()` in controller to customize test data source lookup
- Add additional trigger endpoints by inheriting `DCIClientTriggerController`

### Dependencies

`spp_dci_client`
