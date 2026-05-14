### Writing CEL rules against DCI-backed variables

CEL accessors are **vendor-neutral**. The eligibility rule reads the semantic concept; the vendor identity lives in configuration records.

```
has_disability == true && age_years(r.birthdate) >= 18
```

The bridge does not change CEL syntax. To switch from one DCI registry to another (OpenG2P → national DR, mock → production), change the data source configuration; CEL rules are not edited.

### Configuring a DCI-backed variable manually

1. Create a `spp.dci.data.source` record with `auth_type`, `base_url`, `registry_type`, and OAuth2 credentials.
2. Optional: set the **Vendor Adapter** field (defined here as a Selection field with an empty selection; vendor presets extend it via `selection_add`). Set when a vendor preset registered its adapter — e.g., `openg2p`, `openspp` — so the bridge dispatcher routes through the vendor-specific service. Leave blank for sources that speak vanilla SPDCI.
3. Create a `spp.data.provider` and set `dci_data_source_id` to the source above.
4. Create or repurpose a `spp.cel.variable`:
   - `source_type = 'external'`
   - `external_provider_id` = the provider
   - `dci_attribute_path` = the dotted path into the DCI response payload (e.g., `has_disability`, `severity.code`, `functional_scores.cognition`)
   - `cache_strategy = 'ttl'` (or `'manual'`)
   - `cache_ttl_seconds` = TTL in seconds (300 for demo, 86400 for production)
   - `external_failure_policy` = null / last_known / fail

For typical OpenG2P deployments install `spp_dci_openg2p`; for an OpenSPP-DR instance install `spp_dci_openspp_dr` — each ships a permanent preset.

### Pre-warm behaviour

When `Enroll Eligible` / `Import Eligible` runs at the program level, the bridge eagerly pre-warms **every active DCI-backed CEL variable** for the cohort, regardless of which variables the program's specific CEL rule references. This is by design — the executor's SQL fast path needs a fresh cache for any `metric()` accessor the rule could reference, and parsing the rule up front to extract referenced names was traded off for simplicity. Side effect: a program that only checks `has_disability` still produces audit rows for `is_poor` and any other active SR variables in the cohort.

To exclude a variable from the pre-warm, set `state='inactive'` and `active=False` on the `spp.cel.variable` record. The pre-warm filter applies `("active", "=", True)`, so inactive variables are skipped — useful for deferred-feature placeholders. Such variables are also unavailable to CEL rules (compound rules referencing them evaluate the comparison against null, which fails the filter).

### Failure policies

| Policy       | Behaviour                                                            |
| ------------ | -------------------------------------------------------------------- |
| `null`       | Default. Errored subjects cache as null; CEL evaluates against null. |
| `last_known` | Surface most recent non-null cached value, regardless of expiry.     |
| `fail`       | Propagate the exception as UserError. Eligibility check aborts.      |

### Audit

Every DCI fetch records one row in `spp.dci.fetch.audit`:

- Navigate to the menu surfaced via `view_dci_fetch_audit_list`
- Filter by variable, provider, result (ok / not_found / error)
- Read access for all internal users; write access for spp admin only
