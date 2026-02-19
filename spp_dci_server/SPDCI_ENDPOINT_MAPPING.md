# SPDCI Registry Endpoint Mapping

This document describes the SPDCI-compliant registry endpoint structure implemented in
OpenSPP.

## Overview

OpenSPP now supports both long-form and short-form registry endpoints for compliance
with SPDCI (Social Protection Digital Convergence Initiative) path conventions.

## Endpoint Structure

### Social Registry (Implemented)

| Short-form Path   | Long-form Path                 | Module                  | Status         |
| ----------------- | ------------------------------ | ----------------------- | -------------- |
| `/sr/sync/search` | `/registry/social/sync/search` | `spp_dci_server_social` | ✅ Implemented |
| `/sr/sync/notify` | `/registry/social/sync/notify` | `spp_dci_server_social` | ✅ Implemented |

### Disability Registry (Planned)

| Short-form Path   | Long-form Path                     | Module                      | Status     |
| ----------------- | ---------------------------------- | --------------------------- | ---------- |
| `/dr/sync/search` | `/registry/disability/sync/search` | `spp_dci_server_disability` | ⏳ Planned |
| `/dr/sync/notify` | `/registry/disability/sync/notify` | `spp_dci_server_disability` | ⏳ Planned |

**Current Behavior**: Returns HTTP 501 NOT IMPLEMENTED with appropriate error messages.

### Civil Registry (Planned)

| Short-form Path     | Long-form Path               | Module                | Status     |
| ------------------- | ---------------------------- | --------------------- | ---------- |
| `/crvs/sync/search` | `/registry/crvs/sync/search` | `spp_dci_server_crvs` | ⏳ Planned |
| `/crvs/sync/notify` | `/registry/crvs/sync/notify` | `spp_dci_server_crvs` | ⏳ Planned |

**Current Behavior**: Returns HTTP 501 NOT IMPLEMENTED with appropriate error messages.

### Farmer Registry (Planned)

| Short-form Path   | Long-form Path                 | Module                  | Status     |
| ----------------- | ------------------------------ | ----------------------- | ---------- |
| `/fr/sync/search` | `/registry/farmer/sync/search` | `spp_dci_server_farmer` | ⏳ Planned |
| `/fr/sync/notify` | `/registry/farmer/sync/notify` | `spp_dci_server_farmer` | ⏳ Planned |

**Current Behavior**: Returns HTTP 501 NOT IMPLEMENTED with appropriate error messages.

## Implementation Details

### Module: `spp_dci_server_social`

**New Files:**

- `/routers/sr_alias.py` - SPDCI short-form endpoints for Social Registry

**Modified Files:**

- `/models/fastapi_endpoint_social.py` - Added `sr_alias_router` to the DCI API

**Endpoints:**

- `POST /sr/sync/search` - Synchronous search for social registry records
- `POST /sr/sync/notify` - Receive notifications about social registry changes

### Module: `spp_dci_server`

**New Files:**

- `/routers/registry_aliases.py` - SPDCI short-form endpoints for future registry types

**Modified Files:**

- `/models/fastapi_endpoint_dci.py` - Added registry alias routers (DR, CRVS, FR)

**Endpoints:**

- `POST /dr/sync/search` - Disability Registry search (stub)
- `POST /dr/sync/notify` - Disability Registry notify (stub)
- `POST /crvs/sync/search` - Civil Registry search (stub)
- `POST /crvs/sync/notify` - Civil Registry notify (stub)
- `POST /fr/sync/search` - Farmer Registry search (stub)
- `POST /fr/sync/notify` - Farmer Registry notify (stub)

## Usage Examples

### Social Registry Search (Implemented)

```bash
# Using short-form path (SPDCI-compliant)
curl -X POST "https://openspp-instance/dci/sr/sync/search" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-123",
    "search_request": [
      {
        "reference_id": "ref-1",
        "search_criteria": {
          "reg_type": "SOCIAL_REGISTRY",
          "query_type": "idtype-value",
          "query": {...}
        }
      }
    ]
  }'

# Using long-form path (also supported)
curl -X POST "https://openspp-instance/dci/registry/social/sync/search" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Disability Registry Search (Stub - Returns 501)

```bash
# Using short-form path
curl -X POST "https://openspp-instance/dci/dr/sync/search" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-456",
    "search_request": [...]
  }'

# Response (HTTP 501):
{
  "transaction_id": "txn-456",
  "search_response": [
    {
      "reference_id": "ref-1",
      "timestamp": "2024-01-15T10:30:00Z",
      "status": "rjct",
      "status_reason_code": "NOT_IMPLEMENTED",
      "status_reason_message": "Disability Registry not yet implemented. Will be available in spp_dci_server_disability module."
    }
  ]
}
```

## Testing SPDCI Compliance

The implementation allows SPDCI compliance tests to be run against OpenSPP:

1. **Social Registry**: Full functionality available at `/sr/*` endpoints
2. **Other Registries**: Graceful "not implemented" responses at `/dr/*`, `/crvs/*`, and
   `/fr/*` endpoints

This ensures that compliance testing frameworks can discover all expected endpoints and
receive appropriate responses.

## Adding New Registry Types

To add a new registry type (e.g., Disability Registry):

1. **Create module**: `spp_dci_server_disability`
2. **Add routers**: Create `/routers/disability_search.py` with long-form paths
3. **Add aliases**: Create `/routers/dr_alias.py` with short-form paths
4. **Update endpoint model**: Extend `fastapi.endpoint` to include the new routers
5. **Remove stub**: Update `spp_dci_server/routers/registry_aliases.py` to remove the DR
   stub
6. **Update documentation**: Update this file with implementation status

## Architecture Notes

- **Short-form paths** (`/sr/*`, `/dr/*`, etc.) are SPDCI standard for interoperability
- **Long-form paths** (`/registry/social/*`, etc.) are OpenSPP internal convention
- Both path styles are supported simultaneously for maximum compatibility
- Each registry type is implemented as a separate module for modularity
- Stub endpoints return HTTP 501 to indicate "not yet implemented" per REST standards

## References

- SPDCI Specification: [Link to SPDCI documentation]
- DCI Protocol: `spp_dci` module
- FastAPI Integration: `fastapi` Odoo addon
