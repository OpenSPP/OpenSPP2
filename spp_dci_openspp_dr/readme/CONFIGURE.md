### Launching the DR container

The DR runs as a separate OpenSPP container alongside the SP. From the
repo root:

```bash
./spp start                                      # SP via the project's CLI
docker compose -f docker-compose.dr.yml up -d    # DR standalone
```

The DR joins the SP project's existing Docker network (`openspp2_openspp`
by default) so the SP can reach it at `http://openspp-dr:8069` over the
in-network DNS name. The host can browse the DR UI at
`http://localhost:8070` (admin/admin). If your SP project is named
something other than `openspp2`, set `OPENSPP_NETWORK=<project>_openspp`
before launching.

### After installing this module

The preset auto-creates a DCI data source, CEL provider, and `has_disability` variable binding wired against `http://openspp-dr:8069/dci_api/v1/disability/registry/sync/search` (the docker-compose default for the demo).

1. Navigate to **Custom > DCI > Configuration > Data Sources**.
2. Open the `openspp_dr` data source.
3. Verify (or adjust) **Base URL** — defaults to `http://openspp-dr:8069`. For a non-Docker deployment, replace with the real hostname.
4. **Sender ID** / **Receiver ID** — placeholders are pre-populated. Replace with what the DR operator expects.
5. Click **Test Connection**. State should flip to `Active`.

For real deployments, change `auth_type` to `oauth2` and populate `oauth2_token_url`, `oauth2_client_id`, `oauth2_client_secret`. Attach a DCI Signing Key under **Custom > DCI > Configuration > Signing Keys** if the deployment requires signed messages.

### Required dev-mode flags on the DR for the demo

The DR's signature + bearer-token middleware blocks unsigned/unauthenticated requests by default. For the demo (where the SP sends unsigned envelopes with no bearer token), set TWO system parameters on the DR's `openspp_dr` database — both are required, either alone is insufficient:

```bash
docker compose -f docker-compose.dr.yml exec openspp-dr odoo shell -d openspp_dr --no-http
>>> env['ir.config_parameter'].sudo().set_param('dci.allow_unsigned_requests', 'true')
>>> env['ir.config_parameter'].sudo().set_param('dci.bypass_bearer_auth', 'true')
>>> env.cr.commit()
```

Then restart the DR (`docker compose -f docker-compose.dr.yml restart openspp-dr`). On the first request, the DR log emits a one-time `CRITICAL: SECURITY WARNING: DCI signature verification is DISABLED!` line — that confirms the bypass is active. **Production deployments must leave both at `false`** and register the SP's public key via the DR's DCI Sender Registry.

### UIN vocabulary code

This preset does NOT seed the UIN code on the system `urn:openspp:vocab:id-type` vocabulary. The collision against `spp_dci_openg2p` (which also seeds UIN) forced its removal — see the `spp_dci_openspp_dr` Phase fix commit. On a fresh SP database, install `spp_dci_openg2p` first (it owns the UIN seed), or seed UIN manually before installing this preset. The tests use `get_or_create_local` to be resilient either way.

### Demo data: how to make partners look up the right DR record

The dispatcher's `OpenSPPDRService._get_partner_identifier` priority order picks the SP-side partner's first matching reg_id type:

```
UIN > DRN > NATIONAL_ID > NID > (first available)
```

Tag your SP-side test partners with one of these identifier types using a value that matches a reg_id on the DR-side partner. The DR's `DisabilitySearchService` looks up partners by `spp.registry.id.value`, so the same value must exist on both sides.

### When upstream DRService is fixed

The vendor-specific path is opt-in. If `spp_dci_client_dr.DRService` ever starts unwrapping `data.reg_records[0]` correctly, clear the `vendor` field on the data source. The dispatcher's override falls through to upstream `_handler_dr` → `DRService` automatically — no code change required.
