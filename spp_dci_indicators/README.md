# OpenSPP DCI Indicators

Connects OpenSPP's CEL eligibility/indicator engine to external DCI-compliant registries
(CRVS, Disability Registry). Registry data is fetched over the DCI protocol, cached
locally, and becomes usable in any CEL expression.

## How it works

```
DCI Data Source (connection: URL, OAuth2, registry type)
      ▲ linked via the "DCI Integration" tab
Data Provider (becomes "DCI-backed")
      ▲ External Source on the variable
Studio Variable (e.g. r.dci.crvs.is_alive)
      │
      │  Sync DCI Values (action / cron) — real DCI calls, results cached
      ▼
spp.data.value cache (TTL per variable)
      ▼
Any CEL expression: eligibility, indicators, compliance…
```

Values are fetched at **sync time** and cached with a TTL. CEL evaluation compiles to
SQL over the cache and **never calls a registry per record** — that is what lets
eligibility scale to full populations. Freshness is controlled by when you sync and each
variable's TTL.

## CEL expression examples

```python
# Check if person is alive (no death record in CRVS)
r.dci.crvs.is_alive == true

# Check if birth was registered
r.dci.crvs.birth_verified == true

# Parameterized: check for a specific CRVS event
r.dci.crvs.has_event('death') == true

# Check disability status
r.dci.dr.has_disability == true

# Parameterized: functional severity score for a disability type
r.dci.dr.severity('Vision') >= 3

# Combined eligibility criteria
r.dci.crvs.is_alive == true and r.dci.dr.has_disability == true and age_years(me.birthdate) >= 18
```

## Available variables

| Accessor                                                        | Type   | Meaning                         |
| --------------------------------------------------------------- | ------ | ------------------------------- |
| `r.dci.crvs.is_alive`                                           | bool   | no death event recorded in CRVS |
| `r.dci.crvs.birth_verified`                                     | bool   | birth registration exists       |
| `r.dci.crvs.has_event('birth'\|'death')`                        | bool   | parameterized event check       |
| `r.dci.dr.has_disability`                                       | bool   | disability registered in DR     |
| `r.dci.dr.assessed`                                             | bool   | functional assessment exists    |
| `r.dci.dr.vision_severe` / `hearing_severe` / `mobility_severe` | bool   | functional score ≥ 3            |
| `r.dci.dr.severity('Vision'\|'Hearing'\|'Mobility')`            | number | functional score (0–4)          |

Parameterized methods take arguments from a **fixed, pre-synced set**: each (person,
argument) pair is cached as its own row, keyed by the argument (`params_hash`).
Arbitrary/dynamic arguments are not supported.

> **Planned, not yet wired:** IBR and Social Registry variables, and
> `r.dci.crvs.is_married` (no outbound CRVS marriage query). The corresponding variable
> records exist but return no data until their fetch handlers are implemented.

## Setup

1. **DCI Data Source** — _Settings → Technical → DCI → Configuration → Data Sources_:
   configure the registry connection (base URL, OAuth2, registry type) and **Test
   Connection**.
2. **Data Provider** — _Settings → Technical → CEL Domain → Data Management → Data
   Providers_: open the **DCI Integration** tab and link the Data Source. The provider
   becomes _DCI-backed_; its own Base URL/Authentication are ignored at runtime.
3. **Variable** — _Studio → Variables_: set the variable's **External Source** to that
   provider.
4. **Sync** — select registrants → **Action ▸ Sync DCI Values** (or enable the daily
   cron _"DCI: Sync CEL metrics"_, disabled by default). Registrants need an identifier
   (BRN/UIN/national id…) that the registry recognizes.

See [USAGE.md](USAGE.md) for a full walkthrough, the variable reference, and
troubleshooting.

## Architecture

| Component                      | Role                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `data_provider_dci.py`         | provider ↔ DCI Data Source bridge (`dci_data_source_id`, `is_dci_backed`)                                 |
| `dci_cel_fetcher.py`           | outbound fetch per metric; parameterized-method materialization; the `sync_for_partners`/cron entry points |
| `data_cache_manager_dci.py`    | routes DCI-backed variables through the fetcher; caches under the accessor key                             |
| `cel_variable_resolver_dci.py` | resolves the dotted `*.dci.*` accessors; rewrites method calls into params-carrying `metric()` lookups     |

## Dependencies

- `spp_dci_client` (+ `spp_dci_client_crvs`, `spp_dci_client_dr`, `spp_dci_client_ibr`)
  — DCI protocol clients
- `spp_cel_domain` — CEL engine, variables, `spp.data.value` cache
- `spp_studio` — variable management UI

## License

LGPL-3

## Author

OpenSPP.org
