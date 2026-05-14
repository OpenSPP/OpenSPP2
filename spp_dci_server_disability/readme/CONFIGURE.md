### After installing this module

The endpoint is live at `https://<base_url>/dci_api/v1/disability/registry/sync/search` (the `/dci` prefix comes from the FastAPI endpoint configuration on `spp_dci_server`).

1. Verify the DCI FastAPI endpoint is active: **Custom > Technical > FastAPI > Endpoints**, ensure the row with `app=dci_api` is enabled.
2. Optionally seed test partners with disability data and a known reg_id value so SP-side queries return matches.
3. Confirm the stub is gone: a `POST` to `/dci_api/v1/disability/registry/sync/search` should now return HTTP 200 with a real SearchResponse (not 501).

### Signing keys

The endpoint signs response envelopes using the active `spp.dci.signing.key`. If no active key is configured, responses are emitted unsigned — fine for the demo, not for production.

### Identifier resolution

The service looks up partners by `spp.registry.id.value == search_text`. Match the SP-side preset's identifier scheme so the same value is sent and recognised:

- OpenSPP-DR ships UIN (and any other `spp.vocabulary.code` your registry uses)
- SP-side prefers UIN first; if your data uses NATIONAL_ID, configure `IDENTIFIER_PRIORITY` in the SP-side service accordingly.

### Disability fields

The service reads from the `spp_disability_registry` data model on `res.partner`. Each `res.partner` is the registrant; the disability data is computed from its current approved `spp.disability.assessment`:

| Local field                       | Wire-format key in `reg_records[0]`  |
| --------------------------------- | ------------------------------------ |
| `has_disability` (Boolean)        | `has_disability`                     |
| `disability_severity_id.code`     | `disability_severity_code`           |
| `disability_review_category`      | `disability_review_category`         |
| `disability_next_review`          | `disability_next_review` (ISO date)  |

Missing fields are returned as `False` / `None` rather than raising — `spp_disability_registry` is a soft dependency. Without it, responses carry `has_disability=False` and the other keys default to `None`, which is still SPDCI-valid.

### Authentication and ACLs

The DCI FastAPI endpoint runs as `base.public_user`, which has no Registry access by default. The service uses `sudo()` when reading `spp.registry.id` and `res.partner`. The actual authentication boundary is upstream — DCI signature + bearer-token verification in the middleware. Once the sender_id is accepted by those checks, the service trusts the request.

For demo deployments where you want to bypass both signature and bearer-token verification, set these system parameters on the DR's database (Settings → Technical → Parameters → System Parameters):

| Key | Value | Effect |
|---|---|---|
| `dci.allow_unsigned_requests` | `true` | Skips DCI signature verification |
| `dci.bypass_bearer_auth` | `true` | Skips Authorization-header check |

Both flags trigger a one-time CRITICAL warning in the DR log on the first request after restart. **Production deployments must leave both at `false`** and register sender public keys via the DCI Sender Registry instead.
