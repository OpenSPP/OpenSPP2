# OpenSPP DCI Client Compliance Tests

This module provides DCI client compliance testing infrastructure for validating that
OpenSPP's DCI client implementation correctly sends requests to external registries.

## Purpose

The `spp_dci_client_compliance` module exposes test trigger endpoints that allow the
external `spdci-compliance` test framework to:

1. Trigger DCI client actions (search, subscribe, unsubscribe, txn_status)
2. Validate that requests sent by the client are spec-compliant
3. Test client error handling for various response scenarios

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  spdci-compliance   │────▶│  Trigger Controller  │────▶│  Mock Registry  │
│  (Cucumber tests)   │     │  /dci/test/trigger/* │     │  (validates &   │
└─────────────────────┘     └──────────────────────┘     │   records)      │
         │                           │                    └─────────────────┘
         │                           │                            │
         │                           ▼                            │
         │                  ┌──────────────────┐                  │
         │                  │   DCIClient      │                  │
         │                  │   (spp_dci_      │──────────────────┘
         │                  │    client)       │
         │                  └──────────────────┘
         │
         ▼
┌─────────────────────┐
│  Admin API          │
│  /admin/requests    │◀─────────────── (assertions on recorded requests)
└─────────────────────┘
```

## Endpoints

### Test Triggers

| Endpoint                        | Method | Description                        |
| ------------------------------- | ------ | ---------------------------------- |
| `/dci/test/trigger/health`      | GET    | Health check                       |
| `/dci/test/trigger/search`      | POST   | Trigger search request             |
| `/dci/test/trigger/subscribe`   | POST   | Trigger subscribe request          |
| `/dci/test/trigger/unsubscribe` | POST   | Trigger unsubscribe request        |
| `/dci/test/trigger/txn_status`  | POST   | Trigger transaction status request |

### Request Examples

**Search:**

```json
POST /dci/test/trigger/search
{
    "query_type": "idtype-value",
    "query": {"type": "UIN", "value": "123456789"},
    "record_type": "PERSON",
    "page": 1,
    "page_size": 10
}
```

**Subscribe:**

```json
POST /dci/test/trigger/subscribe
{
    "event_types": ["REGISTER", "UPDATE"],
    "callback_url": "http://client/callback"
}
```

## Usage

### Running Client Compliance Tests

```bash
# From project root (openspp-odoo-19-migration/)

# Option 1: Use invoke task (recommended)
invoke dci-client-compliance

# Option 2: Manual setup
# 1. Start mock registry
cd dci/submodules/spdci-compliance
npm run mock-server:social

# 2. Install module
invoke resetdb --modules=spp_dci_client_compliance

# 3. Run tests
CLIENT_TRIGGER_URL=http://localhost:19069/dci/test/trigger \
MOCK_REGISTRY_ADMIN_URL=http://localhost:3335/admin \
npx cucumber-js --tags @profile=spmis-client
```

### Test Data Source

The module creates a test data source pointing to the mock registry:

| Field         | Value                     |
| ------------- | ------------------------- |
| Name          | DCI Compliance Test       |
| Base URL      | http://mock_registry:3335 |
| Registry Type | social                    |
| Sender ID     | spmis.compliance.test     |

You can override the mock registry URL via system parameter:

```
dci.client_compliance.mock_registry_url = http://your-mock:3335
```

## Dependencies

- `spp_dci_client`: DCI client implementation

## Security Notes

- The trigger endpoints use `auth="none"` to allow external test frameworks to call them
- This module should only be installed in test/development environments
- The `is_compliance_test` flag on data sources identifies test configurations

## Related Modules

- `spp_dci_client`: Core DCI client implementation
- `spp_dci_compliance`: Server-side compliance testing (for our DCI server)
