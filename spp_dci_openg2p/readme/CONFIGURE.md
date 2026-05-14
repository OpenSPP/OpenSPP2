### After installing this module

The preset auto-creates a DCI data source, CEL provider, and CEL variable wired against the OpenG2P playground at `partner-registry.play.openg2p.org`. The playground does not require authentication for the demo — the bridge can call it out of the box.

1. Navigate to **Custom > DCI > Configuration > Data Sources**.
2. Open the `openg2p_dr` data source.
3. Verify (or adjust) **Base URL** — defaults to `https://partner-registry.play.openg2p.org`.
4. The **Search Endpoint** is set to `/dci/registry/sync/search` (OpenG2P uses the `/dci` prefix).
5. **Sender ID** / **Receiver ID** — placeholder values are pre-populated. Replace with what the OpenG2P operator expects from your deployment.
6. Click **Test Connection**. State should flip to `Active`.

For real OpenG2P deployments (not the playground), change `auth_type` to `oauth2` and populate `oauth2_token_url`, `oauth2_client_id`, `oauth2_client_secret`. Attach a DCI Signing Key under **Custom > DCI > Configuration > Signing Keys** if the deployment requires signed messages.

### FR-as-DR pretense (demo-only)

The OpenG2P playground exposes a **Farmer Registry** (FR), not a Disability Registry (DR). Per the SPDCI schema:

```
reg_type:        ns:org:RegistryType:Social
reg_record_type: spdci-extensions-dci:Farmer
```

Until OpenG2P publishes a real DR endpoint, this preset treats FR as a DR stand-in:

- The data source is configured with `registry_type='DR'` so the bridge dispatcher routes to the standard `_handler_dr`.
- `vendor='openg2p'` on the data source triggers the preset's dispatcher override, which uses `OpenG2PFRService` instead of upstream `DRService`.
- `OpenG2PFRService` queries OpenG2P's Farmer Registry. **Presence of any farmer record for a partner → `has_disability=True`**. Absence (or `REG-ERR-001 REGISTER_NOT_FOUND`) → null → fails the eligibility filter.
- The CEL surface stays exactly `has_disability == true`. Only this service's interpretation is the pretense.

Audience-facing this looks like a real DR lookup. Operationally it tests the full DCI round-trip with OpenG2P's actual playground.

### Demo data: which identifiers exist in the OpenG2P playground?

Ask the OpenG2P team for sample identifiers that exist in their Farmer Registry. Configure your test partners with those identifiers (under their **External Identifiers** / `reg_ids`), and the dispatcher's `OpenG2PFRService._get_partner_identifier` priority order will pick them up:

```
UIN > DRN > NATIONAL_ID > NID > (first available)
```

Partners with no matching identifier are recorded in `spp.dci.fetch.audit` as `result='not_found'` and excluded from `has_disability == true` matches.

### Migration plan — when OpenG2P publishes a real Disability Registry

The migration is purely configuration; no code or data changes:

| Step | What to change |
|---|---|
| 1. Point at the new URL | Edit `base_url` on `openg2p_dr` data source (UI) |
| 2. Switch from FR pretense to real DR | Clear the `vendor` field on the data source (set blank). The dispatcher's override falls through to the standard `_handler_dr` → upstream `DRService`. |
| 3. Verify OpenG2P's DR conforms to standard DCI shapes | Run a search; if you get `rjct.search_criteria.invalid: query.value.id_type is required` or response unwrap fails, OpenG2P's DR has the same query/response quirks as their FR. Keep `vendor='openg2p'` set and extend `OpenG2PFRService` to query the DR `reg_record_type`. Track this in ADR-023 v2 work. |
| 4. The CEL accessor stays `has_disability` | No CEL rule changes. Cached values will become real `has_disability` booleans from the DR record. |

In words: clear one field on the data source, and OpenSPP starts reading real disability data from OpenG2P with no other edits anywhere.

### Cache TTL

The preset ships with `cache_ttl_seconds = 300` (5 minutes) on the `has_disability` variable so the DCI round-trip is visible during demos. For production, raise to 86400 (24h) or higher via the `spp_studio.var_has_disability` form.

### Switching to a different DCI Disability Registry vendor

If you target a non-OpenG2P registry, the preset is the wrong starting point — clone it as `spp_dci_<vendor>` and adjust:

- The data source's `base_url` and `vendor` field
- The service class (mirror `OpenG2PFRService` for that vendor's quirks)
- The dispatcher override's branch
