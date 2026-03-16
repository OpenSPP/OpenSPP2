### Prerequisites

Before testing the Change Request API, ensure you have:

1. A running OpenSPP instance with `spp_api_v2_change_request` installed
2. An API client configured with `change_request:all` scope (or individual scopes per endpoint)
3. At least one registrant with an external identifier (e.g., via `spp.registry.id`)
4. At least one active Change Request type (e.g., `edit_individual`)

**Setting up an API client**

Navigate to **Settings > Technical > FastAPI > Endpoints**, open the OpenSPP API V2 endpoint,
and create an API client under the **Clients** tab. Configure scopes for the `change_request`
resource. Use `All Actions` for testing, or assign granular scopes:

- `Read` — list types, read and search change requests
- `Create` — create new change requests
- `Update` — update detail data, submit for approval, reset to draft
- Approve and Apply actions require the `All Actions` scope

**Obtaining an access token**

All endpoints (except `$types` listing) require a Bearer token. Obtain one via the OAuth 2.0
Client Credentials flow:

```bash
# Replace with your client_id and client_secret
curl -s -X POST http://localhost:8069/api/v2/spp/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "grant_type": "client_credentials"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "scope": "change_request:all"
}
```

Set the token for subsequent requests:

```bash
TOKEN="eyJhbGci..."
```

### API Endpoints

**1. List Change Request Types**

Discover available CR types and their target registrant types.

```bash
curl -s http://localhost:8069/api/v2/spp/ChangeRequest/\$types \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
[
  {
    "code": "edit_individual",
    "name": "Edit Individual",
    "targetType": "individual",
    "requiresApplicant": false
  },
  {
    "code": "add_member",
    "name": "Add Member",
    "targetType": "group",
    "requiresApplicant": true
  }
]
```

**2. Get Type Field Schema**

Retrieve the JSON Schema for a CR type's detail fields. Use this to discover which fields
are available, their types, and valid values for vocabulary fields.

```bash
curl -s http://localhost:8069/api/v2/spp/ChangeRequest/\$types/edit_individual \
  -H "Authorization: Bearer $TOKEN"
```

Response (abbreviated):

```json
{
  "typeInfo": {
    "code": "edit_individual",
    "name": "Edit Individual",
    "targetType": "individual",
    "requiresApplicant": false
  },
  "detailSchema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "title": "Edit Individual Detail",
    "properties": {
      "given_name": {
        "type": "string",
        "title": "Given Name"
      },
      "family_name": {
        "type": "string",
        "title": "Family Name"
      },
      "birthdate": {
        "type": "string",
        "format": "date",
        "title": "Date of Birth"
      },
      "gender_id": {
        "type": "object",
        "title": "Gender",
        "x-field-type": "vocabulary",
        "x-vocabulary-uri": "urn:iso:std:iso:5218",
        "properties": {
          "system": { "const": "urn:iso:std:iso:5218" },
          "code": {
            "oneOf": [
              { "const": "1", "title": "Male" },
              { "const": "2", "title": "Female" }
            ]
          }
        }
      },
      "phone": {
        "type": "string",
        "title": "Phone Number"
      },
      "email": {
        "type": "string",
        "title": "Email"
      }
    }
  },
  "availableDocuments": [],
  "requiredDocuments": []
}
```

**3. Create a Change Request**

Create a new CR in `draft` status. The `registrant` field uses the external identifier
format `system|value` (not database IDs).

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ChangeRequest",
    "requestType": { "code": "edit_individual" },
    "registrant": {
      "system": "urn:openspp:vocab:id-type",
      "value": "PH-123456789"
    },
    "detail": {
      "given_name": "Maria Elena",
      "family_name": "Santos",
      "phone": "+639171234567"
    },
    "description": "Name correction request"
  }'
```

Response (`201 Created`):

```json
{
  "type": "ChangeRequest",
  "reference": "CR/2026/00001",
  "requestType": { "code": "edit_individual", "name": "Edit Individual" },
  "status": "draft",
  "registrant": {
    "system": "urn:openspp:vocab:id-type",
    "value": "PH-123456789",
    "display": "SANTOS, MARIA"
  },
  "detail": {
    "given_name": "Maria Elena",
    "family_name": "Santos",
    "phone": "+639171234567"
  },
  "isApplied": false,
  "description": "Name correction request",
  "meta": {
    "versionId": "1710000000000000",
    "lastUpdated": "2026-03-16T01:00:00.000000",
    "source": "urn:openspp:api-client:your_client_id"
  }
}
```

The response includes a `Location` header: `/api/v2/spp/ChangeRequest/CR/2026/00001`.

**Create with vocabulary fields**

Use the `system`/`code` format for vocabulary-typed fields (e.g., `gender_id`):

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ChangeRequest",
    "requestType": { "code": "edit_individual" },
    "registrant": {
      "system": "urn:openspp:vocab:id-type",
      "value": "PH-123456789"
    },
    "detail": {
      "given_name": "Maria",
      "gender_id": {
        "system": "urn:iso:std:iso:5218",
        "code": "2"
      },
      "birthdate": "1990-05-15"
    }
  }'
```

**4. Read a Change Request**

Read a CR by its reference number. The reference has three path segments (e.g., `CR/2026/00001`).

```bash
curl -s http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001 \
  -H "Authorization: Bearer $TOKEN"
```

The response includes an `ETag` header with the `versionId`, which can be used for
optimistic locking on updates.

**5. Search Change Requests**

Search with filters and pagination. All filter parameters are optional.

```bash
# Search by registrant
curl -s 'http://localhost:8069/api/v2/spp/ChangeRequest?registrant=urn:openspp:vocab:id-type|PH-123456789' \
  -H "Authorization: Bearer $TOKEN"

# Search by type and status with pagination
curl -s 'http://localhost:8069/api/v2/spp/ChangeRequest?requestType=edit_individual&status=draft&_count=10&_offset=0' \
  -H "Authorization: Bearer $TOKEN"

# Search by date range
curl -s 'http://localhost:8069/api/v2/spp/ChangeRequest?createdAfter=2026-01-01&createdBefore=2026-12-31' \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "data": [
    {
      "type": "ChangeRequest",
      "reference": "CR/2026/00001",
      "requestType": { "code": "edit_individual", "name": "Edit Individual" },
      "status": "draft",
      "registrant": {
        "system": "urn:openspp:vocab:id-type",
        "value": "PH-123456789",
        "display": "SANTOS, MARIA"
      },
      "isApplied": false,
      "meta": { "versionId": "1710000000000000" }
    }
  ],
  "meta": {
    "total": 1,
    "count": 1,
    "offset": 0
  },
  "links": {
    "self": "/api/v2/spp/ChangeRequest?_count=10&_offset=0"
  }
}
```

The `links` object includes `next` and `prev` URLs when more pages are available.

**6. Update Change Request Detail**

Update detail fields on a `draft` CR. Only fields present in the request body are updated;
omitted fields are left unchanged.

```bash
curl -s -X PUT http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "detail": {
      "given_name": "Maria Elena",
      "phone": "+639171234568"
    }
  }'
```

**Optimistic locking with If-Match**

Use the `ETag` value from a previous read to prevent concurrent modification conflicts:

```bash
curl -s -X PUT http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H 'If-Match: "1710000000000000"' \
  -d '{
    "detail": { "email": "maria@example.com" }
  }'
```

Returns `409 Conflict` if the resource was modified since the `ETag` was obtained.

**7. Submit for Approval**

Submit a `draft` CR for the approval workflow.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$submit \
  -H "Authorization: Bearer $TOKEN"
```

The CR status changes to `pending` (or `approved` if auto-approval is configured).

**8. Approve a Change Request**

Approve a `pending` CR. An optional comment can be provided.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "comment": "Verified with supporting documents" }'
```

**9. Reject a Change Request**

Reject a `pending` CR. A reason is required.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$reject \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "reason": "Supporting documents are incomplete" }'
```

The CR status changes to `rejected`. The reason is stored in `rejectionReason`.

**10. Request Revision**

Request changes on a `pending` CR before it can be approved. Notes are required.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$request-revision \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "notes": "Please provide a valid phone number" }'
```

The CR status changes to `revision`. The notes are stored in `revisionNotes`.

**11. Apply an Approved Change Request**

Apply an `approved` CR to update the registrant's record.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$apply \
  -H "Authorization: Bearer $TOKEN"
```

On success, `isApplied` becomes `true` and `appliedDate` is set. If application fails,
`applyError` contains the error message.

**12. Reset to Draft**

Reset a `rejected` or `revision` CR back to `draft` for resubmission.

```bash
curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest/CR/2026/00001/\$reset \
  -H "Authorization: Bearer $TOKEN"
```

After resetting, you can update the detail data and re-submit.

### Error Responses

| Status | Meaning                                  | Example Cause                                 |
| ------ | ---------------------------------------- | --------------------------------------------- |
| 401    | Unauthorized                             | Missing or expired Bearer token               |
| 403    | Forbidden                                | Client lacks the required scope               |
| 404    | Not Found                                | CR reference does not exist                   |
| 409    | Conflict                                 | Version mismatch, wrong state for action      |
| 422    | Unprocessable Entity                     | Invalid type code, unknown detail fields      |
| 500    | Internal Server Error                    | Unexpected server-side failure                |

Error response body:

```json
{ "detail": "Change request not found: CR/9999/99999" }
```

### Full Lifecycle Example

A complete workflow from creation to application:

```bash
# 1. Get token
TOKEN=$(curl -s -X POST http://localhost:8069/api/v2/spp/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"your_id","client_secret":"your_secret","grant_type":"client_credentials"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 2. Discover available fields for the edit_individual type
curl -s http://localhost:8069/api/v2/spp/ChangeRequest/\$types/edit_individual \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Create a change request
REF=$(curl -s -X POST http://localhost:8069/api/v2/spp/ChangeRequest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ChangeRequest",
    "requestType": {"code": "edit_individual"},
    "registrant": {"system": "urn:openspp:vocab:id-type", "value": "PH-123456789"},
    "detail": {"given_name": "Maria Elena", "phone": "+639171234567"}
  }' | python3 -c "import json,sys; print(json.load(sys.stdin)['reference'])")
echo "Created: $REF"

# 4. Submit for approval (REF is e.g. CR/2026/00001)
curl -s -X POST "http://localhost:8069/api/v2/spp/ChangeRequest/${REF}/\$submit" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 5. Approve
curl -s -X POST "http://localhost:8069/api/v2/spp/ChangeRequest/${REF}/\$approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Approved"}' | python3 -m json.tool

# 6. Apply to registrant
curl -s -X POST "http://localhost:8069/api/v2/spp/ChangeRequest/${REF}/\$apply" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
