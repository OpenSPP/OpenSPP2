Extends OpenSPP API V2 with REST endpoints for program cycles. Exposes cycle data including state, period, beneficiary statistics, and navigation between cycles. Uses cycle name as the external identifier and requires OAuth 2.0 authentication with resource-based scopes.

### Key Capabilities

- **Read Cycle**: Retrieve cycle details by name via `GET /Cycle/{identifier}`
- **Search Cycles**: Filter cycles by program, state, start/end dates, or last updated timestamp
- **Pagination**: Support for offset-based pagination with configurable page size (max 100)
- **Statistics**: Expose beneficiary count, entitlement count, payment count, and total amounts
- **Cycle Navigation**: Reference to previous and next cycles in sequence
- **OAuth Scopes**: Extend API client scopes with `cycle` resource type for read operations

### Key Models

| Model                  | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `spp.api.client.scope` | Extended to support `cycle` resource type        |
| `fastapi.endpoint`     | Extended to register Cycle router in API V2 app  |

### Configuration

This module automatically extends the API V2 endpoint when installed. To grant access to cycles:

1. Navigate to **Settings > API Clients** (provided by `spp_api_v2`)
2. Create or edit an API client
3. Grant `cycle` read scope to clients that need cycle access

No additional menu items are added by this module.

### UI Location

No standalone menu. API endpoints are available at:
- `/api/v2/spp/Cycle` - Search cycles
- `/api/v2/spp/Cycle/{identifier}` - Read cycle by name

### Security

Access controlled via OAuth 2.0 client credentials flow. Clients must have `cycle` read scope granted. All cycle operations use `sudo()` internally, so access control is enforced at the API client scope level, not Odoo user groups.

The module does not define Odoo model access rules as it only extends existing models.

### Extension Points

- Override `CycleService.to_api_schema()` to add custom fields to the API response
- Inherit `Cycle` schema to add domain-specific attributes in the `extension` field
- Add search filters by extending `CycleService.search()` to support additional query parameters

### Dependencies

`spp_api_v2`, `spp_programs`
