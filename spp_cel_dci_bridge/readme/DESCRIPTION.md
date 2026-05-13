Bridges OpenSPP's CEL expression engine to external DCI registries. CEL eligibility rules of the form `has_disability == true` automatically fetch values from a configured DCI registry (Disability Registry, CRVS, IBR), cache them in `spp.data.value`, and resolve as standard SQL filters during program enrollment. No CEL grammar changes; the integration sits behind one cache-manager override.

### Key Capabilities

- Override `spp.data.cache.manager._compute_variable_values` to route `source_type='external'` CEL variables linked to a DCI data source through the DCI client family instead of returning empty
- Dispatch by `registry_type` to the appropriate DCI service (`DRService`, `CRVSService`, `IBRService`) with runtime ImportError guards so the bridge installs cleanly when some clients are absent
- Normalize the three inconsistent registry_type conventions used by existing DCI clients (`"DR"`, `"ns:org:RegistryType:Civil"`, `"ibr"`) to a single canonical key for routing
- Apply per-variable `external_failure_policy`: `null` (default; cache as null), `last_known` (surface most recent non-null cached value), `fail` (propagate as UserError)
- Fill missing subjects with explicit None so the cache stays complete across the cohort — letting the CEL executor use the metric SQL fast path instead of falling back to Python evaluation
- Record one `spp.dci.fetch.audit` row per subject per fetch (provider, source, registry, variable, outcome, elapsed_ms, error_message) for compliance

### Key Models

| Model                    | Description                                                            |
| ------------------------ | ---------------------------------------------------------------------- |
| `spp.cel.dci.dispatcher` | AbstractModel routing fetch requests to per-registry-type handlers     |
| `spp.dci.fetch.audit`    | One row per subject per DCI fetch attempt for compliance audit         |

### Schema Extensions

| Model              | Field                       | Purpose                                                  |
| ------------------ | --------------------------- | -------------------------------------------------------- |
| `spp.data.provider`| `dci_data_source_id`        | Links the CEL provider to a DCI data source              |
| `spp.data.provider`| `is_dci_backed` (computed)  | True when the provider routes through DCI                |
| `spp.cel.variable` | `dci_attribute_path`        | Dotted path into the DCI response (e.g., `has_disability`, `functional_scores.cognition`) |
| `spp.cel.variable` | `external_failure_policy`   | Behaviour on fetch failure: null / last_known / fail     |

### Architecture

```
CEL: has_disability == true
        |
        v (resolver)
    metric('has_disability', me) == true
        |
        v (translator -> executor SQL fast path)
    id IN (SELECT subject_id FROM spp_data_value WHERE ...)
        |
        v (populated by precompute, before eligibility runs)
    cache_mgr.precompute_cached_variables(...)
        |
        v (overridden in this module)
    _compute_variable_values(var, subjects)
        |
        v (when var is DCI-backed)
    spp.cel.dci.dispatcher.fetch_values_for_variable(var, subjects)
        |
        v (registry_type='DR')
    DRService.get_disability_status(partner)
        |
        v (writes back)
    spp.data.value rows + spp.dci.fetch.audit rows
```

The cycle pre-fetch hook (`cycle_manager_base._precompute_cycle_cached_variables`) is already wired in `spp_programs` — installing the bridge plus a vendor preset (e.g., `spp_dci_openg2p`) wires the whole flow without further code.

### See Also

- `spp_dci_openg2p` — permanent OpenG2P vendor preset that ships pre-configured data source, provider, and CEL variable wiring
- ADR-023 — decision rationale, alternatives considered, failure modes, future async work
