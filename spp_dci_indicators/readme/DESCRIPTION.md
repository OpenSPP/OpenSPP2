Connects OpenSPP's CEL eligibility/indicator engine to external DCI-compliant
registries (CRVS, Disability Registry). Registry data is fetched over the DCI
protocol at sync time, cached locally with a TTL, and becomes usable in any CEL
expression. CEL evaluation compiles to SQL over the cache and never calls a
registry per record, so eligibility scales to full populations.

### Key Capabilities

- Link a CEL Data Provider to a DCI Data Source via the **DCI Integration** tab,
  making the provider "DCI-backed"
- Fetch and cache registry values per registrant via the **Sync DCI Values**
  action (or the disabled-by-default daily cron)
- Query Civil Registration via `r.dci.crvs.is_alive`, `r.dci.crvs.birth_verified`,
  and the parameterized `r.dci.crvs.has_event('birth'|'death')`
- Query the Disability Registry via `r.dci.dr.has_disability`, `r.dci.dr.assessed`,
  `r.dci.dr.vision_severe`/`hearing_severe`/`mobility_severe`, and the
  parameterized `r.dci.dr.severity('Vision'|'Hearing'|'Mobility')`
- Parameterized methods cache one value per (registrant, argument), keyed via
  `params_hash`; arguments come from a fixed, pre-synced set

### Key Models

| Model                      | Description                                                       |
| -------------------------- | ----------------------------------------------------------------- |
| `spp.data.provider`        | Extended with `dci_data_source_id` / `is_dci_backed` (the bridge) |
| `spp.dci.cel.fetcher`      | Outbound fetch per metric; sync entry points                      |
| `spp.data.cache.manager`   | Extended to route DCI-backed variables through the fetcher        |
| `spp.cel.variable.resolver`| Extended to resolve `*.dci.*` accessors and method calls          |

### Configuration

1. Configure a DCI Data Source (Settings → Technical → DCI → Data Sources) and
   test the connection
2. Link a Data Provider to it via the **DCI Integration** tab
3. Point the DCI variables (Studio → Variables → External Source) at that
   provider
4. Sync: select registrants → **Action ▸ Sync DCI Values** (registrants need an
   identifier the registry recognizes)

### Data

Creates a **DCI Integration** variable category and the predefined variables.
Working today: the CRVS and DR variables listed above. Present but not yet
wired (no fetch handlers): `dci.crvs.is_married`, the IBR variables
(`dci.ibr.*`) and Social Registry variables (`dci.sr.*`).

### Security

No access control rules defined in this module. Access inherits from the CEL
cache (`spp.data.value`) and the DCI client modules.

### Extension Points

- Add a fetch handler in `spp.dci.cel.fetcher` (`_dci_metric_handlers` for
  simple metrics, `DCI_METHOD_ACCESSORS` + `_compute_method_values` for
  parameterized ones)
- Create the matching `spp.cel.variable` record (external source type, `ttl`
  cache strategy, `r.dci.<registry>.<metric>` accessor)

### CEL Expression Examples

```python
# Vital statistics verification
r.dci.crvs.is_alive == true and r.dci.crvs.birth_verified == true

# Parameterized event check
r.dci.crvs.has_event('death') == true

# Disability-based eligibility
r.dci.dr.has_disability == true and r.dci.dr.severity('Mobility') >= 3

# Multi-registry combined criteria
r.dci.crvs.is_alive == true and r.dci.dr.has_disability == true and age_years(me.birthdate) >= 18
```

### Dependencies

`spp_dci_client`, `spp_dci_client_crvs`, `spp_dci_client_dr`,
`spp_dci_client_ibr`, `spp_cel_domain`, `spp_studio`
