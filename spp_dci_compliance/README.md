# OpenSPP DCI Compliance Tests

This module provides DCI (Digital Convergence Initiative) compliance validation test suite for OpenSPP.

## Purpose

The `spp_dci_compliance` module contains automated tests to verify that OpenSPP's DCI implementation conforms to DCI
protocol requirements, particularly for the Social Registry sync search endpoint.

## Features

- **Test Data Fixtures**: Pre-configured test individuals and identifiers matching DCI compliance test cases
- **Common Test Utilities**: Helper methods for building DCI envelopes, search requests, and assertions
- **Compliance Test Suite**: Comprehensive tests validating DCI protocol requirements

## Test Coverage

The module includes compliance tests for:

### Social Registry Sync Search (`/social/registry/sync/search`)

1. **Response Status**: Validates HTTP 200 status on valid requests
2. **Content Type**: Verifies JSON response format
3. **Response Time**: Ensures responses complete within 15 seconds
4. **Schema Validation**: Validates responses conform to DCI SearchResponse schema
5. **Identifier Search**: Tests searching by identifier (idtype-value query)
6. **Pagination**: Verifies pagination parameters work correctly
7. **Expression Queries**: Tests complex expression-based searches
8. **Error Handling**: Validates proper error responses for invalid requests
9. **Batch Requests**: Tests multiple search requests in a single transaction

## Test Data

The module includes test fixtures:

- **Test Individual 847951632**: Matches DR compliance test cases
- **Test Individual with Disability**: For disability information testing
- **Test Household Group**: For group/household search testing
- **Test Household Members**: For member relationship testing

## Dependencies

- `spp_dci`: Core DCI schemas and utilities
- `spp_dci_server`: DCI server infrastructure
- `spp_dci_server_social`: Social Registry DCI endpoints
- `spp_registry`: OpenSPP registry module
- `jsonschema`: Python package for JSON schema validation

## Usage

### Running Tests

```bash
# Run all compliance tests
odoo-bin -d <database> -i spp_dci_compliance --test-enable --stop-after-init

# Run specific test class
odoo-bin -d <database> --test-tags=spp_dci_compliance.TestSRSyncSearchCompliance

# Run with coverage
pytest --cov=spp_dci_compliance --cov-report=html
```

### Using Test Utilities

```python
from odoo.addons.spp_dci_compliance.tests.common import DCIComplianceCommon

class MyDCITest(DCIComplianceCommon):
    def test_something(self):
        # Build search request
        request = self.build_search_request(
            identifier_type="urn:dci:id:uin",
            identifier_value="847951632"
        )

        # Assert valid response
        self.assert_valid_search_response(response)
```

## Architecture

```
spp_dci_compliance/
├── __init__.py
├── __manifest__.py
├── data/
│   ├── test_identifiers.xml    # Test identifier types
│   └── test_individuals.xml    # Test individuals and groups
├── security/
│   └── ir.model.access.csv     # Access rights (empty)
└── tests/
    ├── __init__.py
    ├── common.py               # Base test class and utilities
    └── test_sr_sync_search.py  # Social Registry compliance tests
```

## Contributing

When adding new compliance tests:

1. Follow the existing test naming convention: `test_##_description`
2. Use helper methods from `DCIComplianceCommon` where possible
3. Add clear docstrings explaining what is being tested
4. Ensure tests are independent and can run in any order
5. Use appropriate assertions from the common test class

## Running SPDCI Compliance Tests

The external SPDCI compliance test suite (`spdci-compliance`) validates protocol compliance.

### Quick Start

```bash
# From project root (openspp-odoo-19-migration/)

# If starting with a fresh database, install base DCI modules first:
invoke resetdb --modules=spp_dci_server_social

# Run compliance tests (auto-installs spp_dci_compliance if needed)
invoke dci-compliance --registry=sr
```

### Using Invoke Tasks

```bash
# From project root (openspp-odoo-19-migration/)
invoke dci-compliance --registry=sr        # SR server tests only (recommended)
invoke dci-compliance --tags=@smoke        # Smoke tests only
invoke dci-compliance -v                   # Verbose output
```

The invoke task automatically handles:

1. Initializing git submodules (spdci-compliance test suite)
2. Installing `spp_dci_compliance` module if not already installed
3. Starting sr_compliance container with network aliases
4. Restarting queue_worker so it can resolve sr_compliance hostname
5. Waiting for queue_worker to be ready
6. Running the compliance tests

### Expected Test Results

With `spp_dci_compliance` module installed (sets up test config), you should see:

```
28 scenarios (28 passed)
137 steps (137 passed)
```

| Category              | Pass | Notes                         |
| --------------------- | ---- | ----------------------------- |
| Sync Search           | 5    | Core search functionality     |
| Async Search          | 4    | Async workflow with callbacks |
| Subscribe/Unsubscribe | 4    | Subscription endpoints        |
| Txn Status            | 2    | Transaction status            |
| Security Tests        | 8    | Auth enforcement tests        |
| Negative Tests        | 5    | Error handling                |

**Total: 28/28 passing** (all tests)

### Production Security Testing

To test security enforcement, disable development mode:

```sql
-- In PostgreSQL
DELETE FROM ir_config_parameter WHERE key = 'dci.allow_unsigned_requests';
```

Then security tests should pass (requests without auth will be rejected).

### Bearer Token Authentication

By default, bearer token authentication is **ENFORCED** for all DCI API endpoints. Requests without a valid
`Authorization: Bearer <token>` header will be rejected with HTTP 401.

To bypass bearer auth for testing (NOT recommended for production):

```sql
-- In PostgreSQL or via Odoo System Parameters
INSERT INTO ir_config_parameter (key, value)
VALUES ('dci.bypass_bearer_auth', 'true')
ON CONFLICT (key) DO UPDATE SET value = 'true';
```

To configure accepted bearer tokens:

```sql
-- Comma-separated list of accepted tokens
INSERT INTO ir_config_parameter (key, value)
VALUES ('dci.api_tokens', 'token1,token2,token3')
ON CONFLICT (key) DO UPDATE SET value = 'token1,token2,token3';
```

If `dci.api_tokens` is not set, any non-empty bearer token will be accepted (useful for testing).

### Environment Variables

| Variable             | Description                                     |
| -------------------- | ----------------------------------------------- |
| `API_BASE_URL`       | Target API base URL (include `/social/` for SR) |
| `EXTRA_HEADERS_JSON` | Additional headers as JSON                      |
| `DOMAIN`             | Registry domain: social, crvs, dr, fr, ibr      |
| `DCI_AUTH_TOKEN`     | Bearer token for authentication                 |

## Troubleshooting

### API Returning HTML 404

**Cause:** FastAPI endpoint routes not registered.

**Fix:** The system auto-repairs on first request. If that fails:

```sql
UPDATE "fastapi.endpoint" SET registry_sync = false;
DELETE FROM endpoint_route;
-- Restart Odoo
```

### Tests Fail with Connection Errors

1. Check Odoo is running: `curl http://localhost:19069/web/health`
2. Check DCI API responds: `curl -H "X-Odoo-Database: devel" http://localhost:19069/dci_api/v1/.well-known/jwks.json`
3. Verify routes exist: `SELECT route FROM endpoint_route WHERE route LIKE '%dci%';`

### X-Odoo-Database Header

Multi-database Odoo requires this header. The test script handles this automatically via `--db` option.

### Port Mapping

- **Internal (container):** 8069
- **External (host):** Check your docker-compose (typically 19069)

## References

- [DCI Protocol Specification](https://docs.dci.example/protocol)
- [OpenSPP DCI Architecture](../docs/architecture/dci/)
- [Testing Guidelines](../docs/principles/testing.md)
- [ADR-015: DCI API Integration](../docs/architecture/decisions/ADR-015-dci-api-integration.md)
