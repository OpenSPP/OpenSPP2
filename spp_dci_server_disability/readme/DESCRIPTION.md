Server-side DCI Disability Registry implementation. Replaces the 501 stub at `/dci_api/v1/disability/registry/sync/search` in `spp_dci_server` with a real handler backed by `DisabilitySearchService`, so SP-side OpenSPP instances (or any DCI-compliant client) can query disability data from this OpenSPP-DR instance.

This module turns an OpenSPP deployment into a DCI-compliant Disability Registry. Install it on the registry instance only — not on SP instances that act as DCI clients.

### What this module ships

| Component                                          | Purpose                                                                                                |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `routers/disability_router.py`                     | Real `/dci_api/v1/disability/registry/sync/search` handler; signs and returns a DCI envelope                       |
| `services/disability_search_service.py`            | Parse SearchRequest → look up partner by reg_id → produce SearchResponse with disability fields         |
| `models/fastapi_endpoint_dr.py`                    | Inherits `fastapi.endpoint` to swap the parent's stub router for our real router on the DCI app        |

### Wire format returned

Each successful response item carries `reg_records[0]` as:

```json
{
  "has_disability": true,
  "disability_certified": false,
  "disability_percentage": 50.0,
  "partner_name": "Maria Santos",
  "partner_uid": 12345
}
```

The CEL-bridge SP side reads `has_disability` (not the local field name `is_person_with_disability`) — the mapping happens here.

### What this module does NOT ship

- SR data (use OpenG2P or `spp_dci_server_social` for Social Registry)
- CRVS data (deferred to `spp_dci_server_crvs`)
- Disability data write-back from external systems (this module exposes data, doesn't accept it)

### See Also

- ADR-024 — federated demo topology
- `spp_dci_server` — base server with the stub being replaced
- `spp_cel_dci_bridge` — bridge that produces requests against this endpoint
