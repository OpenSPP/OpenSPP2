REST API extension for pushing and pulling variable data from external systems. Enables external providers (education ministries, health agencies) to submit computed values into the OpenSPP variable cache and retrieve cached values for program eligibility checks. Uses external identifiers for subject resolution and provider-based access control.

### Key Capabilities

- **Push values**: Bulk upsert variable values from external systems with validation and error reporting
- **Pull values**: Retrieve cached variable values by subject external IDs and period keys
- **Invalidate cache**: Mark cached values as stale to force refresh on next computation
- **List variables**: Query available variables with provider and source type filtering

### Key Models

This module extends existing models rather than defining new ones:

| Model                    | Extension                                    |
| ------------------------ | -------------------------------------------- |
| `spp.api.client.scope`   | Adds "data" resource type for scope control  |
| `fastapi.endpoint`       | Registers Data router under `/api/v2/Data/*` |

### Configuration

After installing:

1. Configure data providers via **CEL Domain > Data Management > Data Providers** (`spp.data.provider` from `spp_cel_domain`)
2. Create OAuth 2.0 API client with `data:read` and `data:write` scopes in **Settings > Technical > FastAPI > Endpoints**
3. Associate variables with external providers via `external_provider_id` field on `spp.cel.variable`
4. Set `default_ttl_seconds` on providers to control cache expiration

### UI Location

No standalone menus (API-only module).

**API Endpoints**:
- `POST /api/v2/Data/push` - Push variable values from external systems
- `GET /api/v2/Data/pull` - Pull cached variable values for subjects
- `POST /api/v2/Data/invalidate` - Invalidate cached values to force refresh
- `GET /api/v2/Data/variables` - List available variables with filtering

### Security

OAuth 2.0 scope-based access control (no model-level ACLs):

| Scope         | Access                                            |
| ------------- | ------------------------------------------------- |
| `data:read`   | Pull cached values and list variables             |
| `data:write`  | Push new values and invalidate cache              |

Provider-based access control validates that variables belong to the authenticated client's provider before allowing push or invalidate operations.

### Extension Points

- Override `_resolve_subject_id()` in `routers/data.py` to customize external identifier resolution
- Extend Pydantic schemas in `schemas/data.py` to add metadata fields for domain-specific use cases
- Inherit `DataValueInput` or `DataValueOutput` for additional validation logic

### Dependencies

`spp_api_v2`, `spp_cel_domain`
