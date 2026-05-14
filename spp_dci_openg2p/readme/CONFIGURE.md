### After installing this module

The preset auto-creates a DCI data source, CEL provider, and CEL variable wired against the OpenG2P playground at `partner-registry.play.openg2p.org`. The playground does not require authentication for the demo — the bridge can call it out of the box.

1. Navigate to **Custom > DCI > Configuration > Data Sources**.
2. Open the `openg2p_dr` data source (the xml id is kept for upgrade-path stability; the record now represents an OpenG2P **Social Registry**, see ADR-024).
3. Verify (or adjust) **Base URL** — defaults to `https://partner-registry.play.openg2p.org`.
4. The **Search Endpoint** is set to `/dci/registry/sync/search` (OpenG2P uses the `/dci` prefix).
5. **Sender ID** / **Receiver ID** — placeholder values are pre-populated. Replace with what the OpenG2P operator expects from your deployment.
6. Click **Test Connection**. State should flip to `Active`.

For real OpenG2P deployments (not the playground), change `auth_type` to `oauth2` and populate `oauth2_token_url`, `oauth2_client_id`, `oauth2_client_secret`. Attach a DCI Signing Key under **Custom > DCI > Configuration > Signing Keys** if the deployment requires signed messages.

### OpenG2P plays the Social Registry role

OpenG2P serves Social Registry data over DCI (poverty status, household composition, related attributes). It is not the source of disability data — that lives in a separate OpenSPP-DR instance (see ADR-024 for the federated demo topology).

This preset configures `registry_type='SR'` so the CEL bridge routes through `_handler_sr`, and `vendor='openg2p'` so the preset's dispatcher override selects `OpenG2PSocialService`. The service issues an OpenG2P-canonical request:

- `query_type`: `expression`
- `query.type`: `ns:org:QueryType:expression`
- `query.value`: `{"expression": {"query": {"search_text": {"$eq": <partner_id>}}}}`
- `reg_type` / `reg_record_type`: both literal `"Individual"`
- `consent` and `authorize` blocks attached to every search criteria (purpose code `ELIGIBILITY_CHECK`)

The bridge dispatcher applies each CEL variable's `dci_attribute_path` to the raw OpenG2P record at `data.reg_records[0]`. No vendor-specific synthesis happens in the service layer — variables extract whatever attribute they need by path.

### Demo data: which identifiers exist in the OpenG2P playground?

Ask the OpenG2P team for sample `search_text` values that exist in their Social Registry. Configure your test partners with those identifiers (under their **External Identifiers** / `reg_ids`), and the dispatcher's `OpenG2PSocialService._get_partner_search_text` priority order will pick them up:

```
UIN > DRN > NATIONAL_ID > NID > (first available)
```

Partners with no matching identifier are recorded in `spp.dci.fetch.audit` as `result='not_found'` and excluded from CEL evaluation.

### When OpenG2P's request shape converges on standard DCI

The vendor-specific path is opt-in. If OpenG2P's published API ever drops the namespaced URI query type, the nested `search_text` shape, or the mandatory consent/authorize blocks and aligns with the upstream DCI defaults, clear the `vendor` field on the data source. The dispatcher's override falls through to the bridge's default `_handler_sr` (currently a not-implemented stub; the bridge will gain a standard SR client when one ships).

### Cache TTL

The preset ships with `cache_ttl_seconds = 300` (5 minutes) on every SR variable so the DCI round-trip is visible during demos. For production, raise to 86400 (24h) or higher on each variable form (**Custom > CEL > Variables**).

### Switching to a different SR vendor

If you target a non-OpenG2P Social Registry, the preset is the wrong starting point — clone it as `spp_dci_<vendor>` and adjust:

- The data source's `base_url` and `vendor` field
- The service class (mirror `OpenG2PSocialService` for that vendor's quirks)
- The dispatcher override's branch
