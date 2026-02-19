# OpenSPP API V2

Standards-aligned, consent-respecting API for social protection data exchange.

## Overview

OpenSPP API V2 provides a modern, secure REST API for accessing OpenSPP registry data.
It is designed for:

- **G2P Connect / DCI compliance** - Follows international social protection
  interoperability standards
- **Consent-based access** - All data access requires explicit consent from registrants
- **External identifiers** - Never exposes internal database IDs
- **Namespace URIs** - Uses globally unique URIs for all identifier types
- **Source tracking** - Tracks data provenance per ADR-008

## Key Features

### 1. No Database IDs

All resources are identified by external identifiers with namespace URIs:

```json
{
  "identifier": [
    {
      "system": "urn:gov:ph:psa:national-id",
      "value": "PH-123456789"
    }
  ]
}
```

### 2. OAuth 2.0 Authentication

Client credentials flow with JWT tokens:

```bash
# Get token
curl -X POST http://localhost:8069/api/v2/spp/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }'

# Use token
curl http://localhost:8069/api/v2/spp/Individual/urn:gov:ph:psa:national-id|PH-123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Consent-Based Access Control

Every API response is filtered based on:

- Active consent from the registrant
- Consent scope (which fields can be accessed)
- API client scope (which operations are permitted)

If no consent exists, only minimal data (identifier) is returned.

### 4. Vocabulary System

Uses `spp.vocabulary.code` for coded values:

```python
# Gender is Many2one to spp.vocabulary.code, NOT a string
gender_id.namespace_uri  # "urn:iso:std:iso:5218"
gender_id.code           # "2"
gender_id.display        # "Female"
```

### 5. Source Tracking

All data created/updated via API is tracked:

```python
partner.source_system        # "urn:openspp:api-client:client-123"
partner.collection_method    # "api"
partner.last_update_system   # "urn:openspp:api-client:client-123"
```

## Installation

1. Install dependencies:

   ```bash
   pip install pyjwt
   ```

2. Install the module via Odoo Apps or command line:

   ```bash
   odoo -i spp_api_v2
   ```

3. JWT secret is automatically generated on module install. To customize:

   ```
   Key: spp_api_v2.jwt_secret
   Value: <secure random string>
   ```

   Generate a custom secret:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. Create API client:
   - Go to Configuration > API V2 > API Clients
   - Create new client
   - Copy client_id and client_secret
   - Add scopes (individual:read, individual:create, etc.)

## API Endpoints

### Authentication

- `POST /oauth/token` - Get access token

### Metadata

- `GET /metadata` - Get capability statement (public)

### Individual

- `GET /Individual/{identifier}` - Read by identifier
- `GET /Individual` - Search individuals
- `POST /Individual` - Create individual
- `PUT /Individual/{identifier}` - Update individual

### Group

- `GET /Group/{identifier}` - Read by identifier
- `GET /Group` - Search groups
- `POST /Group` - Create group
- `PUT /Group/{identifier}` - Update group

## Architecture Decisions

This module implements several Architecture Decision Records (ADRs):

- **ADR-007**: Namespace URIs for Identifiers
- **ADR-008**: Source Tracking and Provenance
- **ADR-009**: Terminology System (Vocabulary)

See `docs/architecture/decisions/` for full ADR documentation.

## Security Groups

### Three-Tier Architecture

**Tier 3 - Technical Privileges:**

- `API V2: Read` - Read access to API configuration
- `API V2: Write` - Modify access to API configuration
- `API V2: Create` - Create new API clients

**Tier 2 - User-Facing Groups:**

- `API V2 Viewer` - View API clients and consents
- `API V2 Officer` - Manage consents
- `API V2 Manager` - Full API configuration control

## Configuration

### System Parameters

- `spp_api_v2.jwt_secret` - JWT signing secret (auto-generated on install)
- `spp_api_v2.token_expiration` - Token lifetime in seconds (default: 3600)

### Known Limitations

- **Rate limiting**: The `rate_limit_per_minute` and `rate_limit_per_day` fields on API
  clients are defined but not enforced. Rate limiting middleware will be added in a
  future release.

## Development

### Module Structure

```
spp_api_v2/
├── models/          # Odoo models (API client, consent, etc.)
├── schemas/         # Pydantic schemas for API resources
├── services/        # Business logic (mapping, search, consent)
├── routers/         # FastAPI routers (endpoints)
├── middleware/      # JWT authentication
├── security/        # Access rights
├── data/            # Config and endpoint registration
└── views/           # UI views
```

### Key Service Classes

- `IndividualService` - CRUD and mapping for Individual resource
- `GroupService` - CRUD and mapping for Group resource
- `SearchService` - Search parameter parsing and execution
- `ConsentService` - Consent filtering and access control

## Testing

Tests are located in the `tests/` directory. Run with:

```bash
odoo -i spp_api_v2 --test-enable --stop-after-init
```

## Troubleshooting

### JWT Secret Not Configured

If you see "JWT secret not configured", set it in System Parameters:

```
Settings > Technical > Parameters > System Parameters
Key: spp_api_v2.jwt_secret
Value: <your-secret-key>
```

### No Active Consent

If API returns only identifier, check:

1. Does an active consent exist for this registrant/client?
2. Is the consent scope correct for the resource type?
3. Has the consent expired?

### Invalid Identifier Format

API expects identifiers in format: `{namespace_uri}|{value}`

Example: `urn:gov:ph:psa:national-id|PH-123456789`

## License

LGPL-3

## Authors

- OpenSPP.org
- Newlogic Impact Lab

## Support

- Documentation: https://docs.openspp.org
- Issue Tracker: https://github.com/openspp/openspp-modules/issues
