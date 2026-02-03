REST API endpoints for querying cash and in-kind entitlements via OAuth 2.0 authenticated clients. Exposes entitlement data by external identifiers (codes) without revealing database IDs. Supports filtering by beneficiary, program, cycle, state, and validity dates.

### Key Capabilities

- **Read Entitlement**: Retrieve entitlement by code (UUID-based identifier) via `GET /Entitlement/{identifier}`
- **Search Entitlements**: Query with filters (beneficiary, program, cycle, state, type, dates) via `GET /Entitlement`
- **Cash and In-Kind**: Supports both `spp.entitlement` (cash) and `spp.entitlement.inkind` models
- **Pagination**: Returns paginated bundles with next/previous links (max 100 per page)
- **Scope-Based Access**: Requires `entitlement:read` OAuth scope for all operations

### Key Models

| Model                  | Description                                                 |
| ---------------------- | ----------------------------------------------------------- |
| `spp.api.client.scope` | Extended to add `entitlement` as resource type              |
| `fastapi.endpoint`     | Extended to register entitlement router for `api_v2` app    |

### Configuration

After installing:

1. Navigate to **Settings > Technical > FastAPI Endpoints**
2. Ensure the `api_v2` endpoint is configured
3. Create API clients via **Settings > Technical > API Clients**
4. Grant `entitlement:read` scope to clients needing entitlement access

### UI Location

No UI components. This is a backend API module accessed via HTTP:

- **Read**: `GET /api/v2/spp/Entitlement/{code}`
- **Search**: `GET /api/v2/spp/Entitlement?beneficiary={system|value}&program={name}...`

### Security

No model access rules defined in this module. Security is enforced via OAuth 2.0 client scopes:

- API clients must have `entitlement:read` scope (via `spp.api.client.scope` records)
- Authorization is validated at the router level via `api_client.has_scope("entitlement", "read")`
- Underlying entitlement model access is governed by `spp_programs` module security

### Extension Points

- Inherit `EntitlementService` and override `to_api_schema()` to add custom fields to the API response
- Extend `Entitlement` Pydantic schema to expose additional entitlement attributes
- Override `_search_cash()` or `_search_inkind()` to customize search domain logic

### Dependencies

`spp_api_v2`, `spp_programs`

Auto-installs when both `spp_api_v2` and `spp_programs` are present.
