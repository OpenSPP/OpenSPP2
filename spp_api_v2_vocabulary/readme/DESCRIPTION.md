REST API endpoints for vocabulary lookup and code retrieval. Exposes vocabularies (standardized code lists like gender, relationship types, administrative divisions) through OAuth 2.0-authenticated endpoints. Uses namespace URIs as identifiers rather than database IDs. Auto-installs when both `spp_api_v2` and `spp_vocabulary` are present.

### Key Capabilities

- List all available vocabularies with domain filtering and pagination
- Retrieve vocabulary metadata including name, version, description, and reference URL
- Fetch codes within a vocabulary with support for hierarchical structures
- Filter codes by parent (for hierarchical vocabularies) and include/exclude deprecated codes
- Validate namespace URIs for security (path traversal, null bytes, control characters)

### Key Models

| Model                  | Description                                             |
| ---------------------- | ------------------------------------------------------- |
| `spp.vocabulary`       | Vocabulary definitions exposed via GET endpoints        |
| `spp.vocabulary.code`  | Individual codes within vocabularies                    |
| `spp.api.client.scope` | Extended to add "vocabulary" resource type for OAuth    |
| `fastapi.endpoint`     | Extended to register Vocabulary router in API V2        |

### API Endpoints

- `GET /Vocabulary` - List all vocabularies (supports `domain`, `_count`, `_offset` query params)
- `GET /Vocabulary/{namespace_uri}` - Get vocabulary details by namespace URI (URL-encoded)
- `GET /Vocabulary/{namespace_uri}/codes` - Get codes within a vocabulary (supports `parent_code`, `include_deprecated`, `_count`, `_offset`)

### Configuration

No standalone menu. After installing, configure API access in dependent modules:

1. Navigate to **Settings > Technical > FastAPI > FastAPI Endpoints** (from `fastapi` module)
2. Locate the API V2 endpoint and verify it is active
3. Create OAuth clients under **Social Protection > Configuration > API Clients** (from `spp_api_v2` module)
4. Grant clients the "vocabulary" scope with "read" action

### Security

- Requires OAuth 2.0 authentication via `spp_api_v2` framework
- Requires "vocabulary" scope with "read" action on API client
- No Odoo security groups required (vocabularies are public data, endpoints use sudo())
- Validates namespace URI and parent_code parameters for injection attacks

### Dependencies

`spp_api_v2`, `spp_vocabulary`
