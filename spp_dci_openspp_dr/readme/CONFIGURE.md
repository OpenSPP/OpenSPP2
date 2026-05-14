### After installing this module

The preset auto-creates a DCI data source, CEL provider, and `has_disability` variable binding wired against `http://openspp-dr:8069/dci/disability/registry/sync/search` (the docker-compose default for the demo).

1. Navigate to **Custom > DCI > Configuration > Data Sources**.
2. Open the `openspp_dr` data source.
3. Verify (or adjust) **Base URL** — defaults to `http://openspp-dr:8069`. For a non-Docker deployment, replace with the real hostname.
4. **Sender ID** / **Receiver ID** — placeholders are pre-populated. Replace with what the DR operator expects.
5. Click **Test Connection**. State should flip to `Active`.

For real deployments, change `auth_type` to `oauth2` and populate `oauth2_token_url`, `oauth2_client_id`, `oauth2_client_secret`. Attach a DCI Signing Key under **Custom > DCI > Configuration > Signing Keys** if the deployment requires signed messages.

### Demo data: how to make partners look up the right DR record

The dispatcher's `OpenSPPDRService._get_partner_identifier` priority order picks the SP-side partner's first matching reg_id type:

```
UIN > DRN > NATIONAL_ID > NID > (first available)
```

Tag your SP-side test partners with one of these identifier types using a value that matches a reg_id on the DR-side partner. The DR's `DisabilitySearchService` looks up partners by `spp.registry.id.value`, so the same value must exist on both sides.

### When upstream DRService is fixed

The vendor-specific path is opt-in. If `spp_dci_client_dr.DRService` ever starts unwrapping `data.reg_records[0]` correctly, clear the `vendor` field on the data source. The dispatcher's override falls through to upstream `_handler_dr` → `DRService` automatically — no code change required.
