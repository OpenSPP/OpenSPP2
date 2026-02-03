# spp_api_v2 Test Suite

Comprehensive test suite for OpenSPP API V2 module with **169 test methods** achieving ~95% code coverage.

## Test Files

| File                         | Tests   | Description                         |
| ---------------------------- | ------- | ----------------------------------- |
| `common.py`                  | -       | Base test class and utilities       |
| `test_api_client.py`         | 14      | API client model and authentication |
| `test_consent.py`            | 19      | Consent model and lifecycle         |
| `test_consent_service.py`    | 11      | Consent-based filtering             |
| `test_individual_service.py` | 17      | Individual CRUD and mapping         |
| `test_group_service.py`      | 19      | Group CRUD and mapping              |
| `test_search_service.py`     | 24      | Search functionality                |
| `test_individual_api.py`     | 23      | Individual HTTP endpoints           |
| `test_group_api.py`          | 21      | Group HTTP endpoints                |
| `test_oauth.py`              | 10      | OAuth token endpoint                |
| `test_metadata.py`           | 11      | Capability statement endpoint       |
| **TOTAL**                    | **169** |                                     |

## Quick Start

```bash
# Run all tests
odoo-bin -c /etc/odoo/odoo.conf -d test_db --test-tags=spp_api_v2 --stop-after-init

# Run specific test file
odoo-bin -c /etc/odoo/odoo.conf -d test_db --test-tags=spp_api_v2.test_individual_api --stop-after-init

# Run specific test class
odoo-bin -c /etc/odoo/odoo.conf -d test_db --test-tags=spp_api_v2.test_individual_api.TestIndividualAPIEndpoints --stop-after-init

# Run with coverage report
coverage run --source=spp_api_v2 odoo-bin -c /etc/odoo/odoo.conf -d test_db --test-tags=spp_api_v2 --stop-after-init
coverage report -m
coverage html  # Generate HTML report
```

## Key Test Coverage

### ✅ Critical Requirements

- **No Database IDs**: All responses use external identifiers only
- **Namespace URIs**: All lookups use `namespace_uri` field
- **Consent Filtering**: Field-level access control based on consent
- **Source Tracking**: All creates/updates track source system
- **OAuth 2.0**: Client credentials flow with JWT tokens
- **Error Handling**: All HTTP error codes (400, 401, 403, 404, 409, 422, 500)

### ✅ API Endpoints

- Individual CRUD (Create, Read, Update, Search)
- Group CRUD (Create, Read, Update, Search)
- OAuth token generation
- Capability statement (metadata)

### ✅ Business Logic

- Consent lifecycle (draft, active, expired, revoked)
- Scope management (resource-level and field-level)
- Search with filters (name, date ranges, gender, address)
- Pagination and sorting
- Member relationships in groups

### ✅ Security

- Authentication required for all endpoints (except metadata)
- Scope-based authorization
- Consent-based data filtering
- Legal basis bypass for certain clients

## Test Utilities (common.py)

The `ApiV2TestCase` base class provides helper methods:

```python
# Create test individual
individual = self.create_test_individual(
    name="John Doe",
    identifier_value="IND-001",
    gender_id=self.gender_male.id,
    birthdate=date(1990, 1, 1),
)

# Create test group with members
group = self.create_test_group(
    name="Test Household",
    identifier_value="HH-001",
    members=[(individual, self.relationship_head)],
)

# Create API client with scopes
client = self.create_api_client(
    name="Test Client",
    scopes=[
        {"resource": "individual", "action": "read"},
        {"resource": "group", "action": "search"},
    ],
)

# Create consent
consent = self.create_consent(
    registrant=individual,
    grantee_partner=client.partner_id,
    field_access="all",
)

# Generate JWT token for API testing
token = self.generate_jwt_token(client)
```

## Test Data Setup

Each test case automatically sets up:

- JWT secret configuration parameter
- Test country and state
- Test ID types with namespace URIs
- Gender vocabulary codes (ISO 5218)
- Relationship vocabulary codes

## Coverage Details

See [TEST_COVERAGE.md](./TEST_COVERAGE.md) for detailed coverage report.

## Compliance

✅ Follows OpenSPP testing principles ✅ 85%+ coverage target exceeded ✅ No database IDs exposed in tests ✅ Namespace
URIs used for all lookups ✅ All error scenarios tested ✅ All success scenarios tested ✅ Security scenarios covered
