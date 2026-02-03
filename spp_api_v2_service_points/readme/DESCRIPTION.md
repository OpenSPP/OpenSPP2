REST API extension that exposes Service Point resources through OpenSPP API V2. Enables external systems to search and retrieve service point data via authenticated HTTP endpoints. Uses service point names as external identifiers to avoid exposing database IDs.

### Key Capabilities

- Search service points by name, area, country, contract status, and last updated date
- Read individual service points by identifier (name)
- Paginate search results with configurable page size (1-100 records)
- Filter service points by contract active status and geographic criteria
- Return metadata including version IDs and last updated timestamps for optimistic locking
- Enforce OAuth 2.0 authentication and scope-based authorization

### Extended Models

This module extends existing models from dependencies:

| Model                  | Description                                                      |
| ---------------------- | ---------------------------------------------------------------- |
| `spp.api.client.scope` | Extended to add "service_point" resource type for OAuth scopes   |
| `fastapi.endpoint`     | Extended to register Service Point router in API V2 app          |

### Configuration

No standalone menu. After installing, configure OAuth API clients via base module:

1. Navigate to **Settings > Technical > OAuth API Clients** (from `spp_api_v2`)
2. Open or create an API client
3. Add "Service Point" scope with "Read" permission
4. External systems authenticate via OAuth 2.0 token endpoint
5. Access endpoints at `/api/v2/spp/ServicePoint`

### API Endpoints

- `GET /api/v2/spp/ServicePoint/{identifier}` - Read service point by identifier (URL-encoded name)
- `GET /api/v2/spp/ServicePoint?name=&area=&country=&contractActive=&_lastUpdated=&_count=&_offset=` - Search service points

### Security

Authentication via OAuth 2.0 bearer tokens. Clients must have `service_point:read` scope. All endpoints require authenticated API client with appropriate scope. No model-level access rules defined (security enforced at API layer).

### Extension Points

- Inherit `ServicePointService.to_api_schema()` to add custom fields to API response
- Override `ServicePointService.search()` to customize search domain logic
- Extend `ServicePoint` schema to add module-specific fields in `extension` attribute

### Dependencies

`spp_api_v2`, `spp_service_points`
