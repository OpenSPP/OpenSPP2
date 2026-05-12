Exposes REST API endpoints for managing change requests through the OpenSPP API V2 framework. Allows external systems to create change requests, submit them for approval, and apply approved changes to registrants via OAuth 2.0 authenticated API calls. Uses CR reference numbers (CR/2024/00001) instead of database IDs for all operations. Auto-installs when both `spp_api_v2` and `spp_change_request_v2` are present.

### Key Capabilities

- Create change requests in draft status with registrant and detail data
- Read individual change requests by reference or search with filters (registrant, type, status, dates)
- Update detail data on draft change requests with optimistic locking via If-Match/ETag headers
- Submit draft requests for approval workflow
- Approve, reject, or request revision on pending requests (requires approval scope)
- Apply approved change requests to registrant records
- Reset rejected/revision requests to draft for resubmission
- Discover available CR types and retrieve JSON Schema for type-specific detail fields
- Paginated search results with next/prev navigation URLs

### Key Models

This module extends existing models and does not define new ones.

| Model                      | Usage                                                       |
| -------------------------- | ----------------------------------------------------------- |
| `fastapi.endpoint`         | Extended to register ChangeRequest router with API V2       |
| `spp.api.client.scope`     | Extended to add `change_request` as a resource selection     |
| `spp.change.request`       | CRUD operations via REST API                                |
| `spp.change.request.type`  | Looked up by code; provides type metadata and field schemas  |
| `spp.registry.id`          | Used to resolve registrant identifiers (system\|value)      |

### Configuration

This module automatically extends the existing API V2 endpoint when installed. No additional configuration is required.

To configure OAuth 2.0 clients with appropriate scopes:

1. Navigate to **Settings > Technical > FastAPI > Endpoints** (provided by `spp_api_v2`)
2. Configure OAuth 2.0 clients with appropriate scopes:
   - `change_request:read` - Read and search change requests, list CR types
   - `change_request:create` - Create new change requests
   - `change_request:update` - Update, submit, and reset requests
   - `change_request:approve` - Approve, reject, or request revision
   - `change_request:apply` - Apply approved changes to registrants

### API Endpoints

- `POST /ChangeRequest` - Create new change request
- `GET /ChangeRequest/{reference}` - Read by reference
- `GET /ChangeRequest` - Search with filters and pagination
- `PUT /ChangeRequest/{reference}` - Update detail data
- `POST /ChangeRequest/{reference}/$submit` - Submit for approval
- `POST /ChangeRequest/{reference}/$approve` - Approve request
- `POST /ChangeRequest/{reference}/$reject` - Reject request
- `POST /ChangeRequest/{reference}/$request-revision` - Request revision
- `POST /ChangeRequest/{reference}/$apply` - Apply to registrant
- `POST /ChangeRequest/{reference}/$reset` - Reset to draft
- `GET /ChangeRequest/$types` - List available CR types
- `GET /ChangeRequest/$types/{code}` - Get JSON Schema for a CR type's detail fields

### Security

No model access rules — this module extends existing models only. Access is controlled via OAuth 2.0 scopes on the `change_request` resource. Each endpoint checks `has_scope(resource, action)` and returns 403 Forbidden if the client lacks the required scope. Users must authenticate via the `spp_api_v2` OAuth 2.0 provider.

### Extension Points

- Inherit `ChangeRequestService` to customize serialization, validation, or business logic
- Override router endpoint functions to add custom validation or side effects
- Extend the API schema by inheriting the Pydantic models in `schemas/change_request.py`

### UI Location

No standalone menu — API-only module. The ChangeRequest router is automatically registered with the API V2 endpoint when this module is installed.

### Dependencies

`spp_api_v2`, `spp_change_request_v2`
