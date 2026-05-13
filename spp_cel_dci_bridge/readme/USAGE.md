### Writing CEL rules against DCI-backed variables

CEL accessors are **vendor-neutral**. The eligibility rule reads the semantic concept; the vendor identity lives in configuration records.

```cel
has_disability == true and age_years(r.birthdate) >= 18
```

The bridge does not change CEL syntax. To switch from one DCI registry to another (OpenG2P → national DR, mock → production), change the data source configuration; CEL rules are not edited.

### Configuring a DCI-backed variable manually

1. Create a `spp.dci.data.source` record with `auth_type`, `base_url`, `registry_type`, and OAuth2 credentials.
2. Create a `spp.data.provider` and set `dci_data_source_id` to the source above.
3. Create or repurpose a `spp.cel.variable`:
   - `source_type = 'external'`
   - `external_provider_id` = the provider
   - `dci_attribute_path` = the dotted path into the DCI response payload (e.g., `has_disability`, `severity.code`, `functional_scores.cognition`)
   - `cache_strategy = 'ttl'` (or `'manual'`)
   - `cache_ttl_seconds` = TTL in seconds (300 for demo, 86400 for production)
   - `external_failure_policy` = null / last_known / fail

For typical OpenG2P deployments, install `spp_dci_openg2p` instead of doing the above by hand — it ships a permanent preset.

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
