### After installing this module

The endpoint is live at `https://<base_url>/dci/disability/registry/sync/search` (the `/dci` prefix comes from the FastAPI endpoint configuration on `spp_dci_server`).

1. Verify the DCI FastAPI endpoint is active: **Custom > Technical > FastAPI > Endpoints**, ensure the row with `app=dci_api` is enabled.
2. Optionally seed test partners with disability data and a known reg_id value so SP-side queries return matches.
3. Confirm the stub is gone: a `POST` to `/dci/disability/registry/sync/search` should now return HTTP 200 with a real SearchResponse (not 501).

### Signing keys

The endpoint signs response envelopes using the active `spp.dci.signing.key`. If no active key is configured, responses are emitted unsigned — fine for the demo, not for production.

### Identifier resolution

The service looks up partners by `spp.registry.id.value == search_text`. Match the SP-side preset's identifier scheme so the same value is sent and recognised:

- OpenSPP-DR ships UIN (and any other `spp.vocabulary.code` your registry uses)
- SP-side prefers UIN first; if your data uses NATIONAL_ID, configure `IDENTIFIER_PRIORITY` in the SP-side service accordingly.

### Disability fields

The service reads three fields from `res.partner`:

| Local field                  | Wire-format key in `reg_records[0]` |
| ---------------------------- | ----------------------------------- |
| `is_person_with_disability`  | `has_disability`                    |
| `disability_certified`       | `disability_certified`              |
| `disability_percentage`      | `disability_percentage`             |

Missing fields are returned as `False` / `None` rather than raising — modules that define these fields are not strict dependencies of this server module.
