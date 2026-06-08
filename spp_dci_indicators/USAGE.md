# DCI Indicators Module - Usage Guide

## Quick Start

### 1. Installation

```bash
odoo-bin -d your_database -i spp_dci_indicators --stop-after-init
```

Dependencies installed automatically: `spp_dci_client` (+ CRVS/DR/IBR clients),
`spp_cel_domain`, `spp_studio`.

### 2. Configure a DCI Data Source

1. Go to **Settings → Technical → DCI → Configuration → Data Sources**
2. Create the registry connection: base URL, registry type (e.g. _Civil Registration and
   Vital Statistics (CRVS)_), authentication (e.g. OAuth2 client credentials)
3. Click **Test Connection** — the source should become **Active**

### 3. Link a Data Provider to the DCI Data Source

1. Go to **Settings → Technical → CEL Domain → Data Management → Data Providers** and
   create/open a provider (e.g. "OpenCRVS")
2. Open the **DCI Integration** tab and select the **DCI Data Source**
3. The provider is now _DCI-backed_: variable values are fetched via the DCI protocol
   using the linked source. The provider's own Base URL and Authentication are ignored
   at runtime.

### 4. Point the variables at the provider

1. Go to **Studio → Variables**
2. Open a DCI variable (e.g. `dci.crvs.is_alive`)
3. Set **External Source** to your DCI-backed provider

### 5. Sync DCI values

CEL reads **cached** values (`spp.data.value`, TTL per variable) — sync before using a
variable in eligibility:

- **Manual:** Registrants list → select people → **Action ▸ Sync DCI Values**. A
  notification reports how many values were cached. Real DCI calls are made per
  registrant; the action is idempotent.
- **Scheduled:** enable the cron **"DCI: Sync CEL metrics"** (disabled by default) to
  refresh all registrants daily.
- **Scripted:**

  ```python
  env["spp.dci.cel.fetcher"].sync_for_partners(partner_ids)
  ```

> Registrants must carry an identifier the registry recognizes (e.g. BRN/UIN as a
> Registrant ID). People without a recognized identifier are skipped.

## Use in Program Eligibility

1. Navigate to **Programs → Your Program → Eligibility Manager**
2. Select **"CEL Expression"** mode
3. Enter the expression, **Test Expression**, **Preview Beneficiaries**, save

### Example 1: Disability Program

Must be alive, severe mobility disability, 18+:

```python
crvs.dci.is_alive == true and
dr.dci.severity('Mobility') >= 3 and
age_years(me.birthdate) >= 18
```

### Example 2: Child Support Program

Birth verified, under 5:

```python
crvs.dci.birth_verified == true and
age_years(me.birthdate) < 5
```

### Example 3: Combined criteria

Alive, and either disabled or elderly:

```python
crvs.dci.is_alive == true and
(dr.dci.has_disability == true or age_years(me.birthdate) >= 60)
```

## Variable Reference

### CRVS (Civil Registration and Vital Statistics)

| Accessor                               | Type | Description               | Example                               |
| -------------------------------------- | ---- | ------------------------- | ------------------------------------- |
| `crvs.dci.is_alive`                    | bool | no death event in CRVS    | `crvs.dci.is_alive == true`           |
| `crvs.dci.birth_verified`              | bool | birth registration exists | `crvs.dci.birth_verified == true`     |
| `crvs.dci.has_event('birth'\|'death')` | bool | parameterized event check | `crvs.dci.has_event('death') == true` |

### DR (Disability Registry)

| Accessor                                                      | Type   | Description                  | Example                          |
| ------------------------------------------------------------- | ------ | ---------------------------- | -------------------------------- |
| `dr.dci.has_disability`                                       | bool   | any registered disability    | `dr.dci.has_disability == true`  |
| `dr.dci.assessed`                                             | bool   | functional assessment exists | `dr.dci.assessed == true`        |
| `dr.dci.vision_severe` / `hearing_severe` / `mobility_severe` | bool   | score ≥ 3                    | `dr.dci.vision_severe == true`   |
| `dr.dci.severity('Vision'\|'Hearing'\|'Mobility')`            | number | functional score (0–4)       | `dr.dci.severity('Vision') >= 3` |

**Severity levels:** 1 no difficulty · 2 some difficulty · 3 a lot of difficulty · 4
cannot do. (Scores depend on the registry returning functional assessment data.)

### Parameterized methods

`severity(...)` and `has_event(...)` take an argument from a **fixed, enumerated set**
(listed above). Each (person, argument) is synced and cached as its own value — an
argument outside the enumerated set simply matches nothing.

### Planned (not yet wired)

`crvs.dci.is_married` and the IBR / Social Registry variables (`ibr.dci.*`, `sr.dci.*`)
exist as variable records but have no fetch handlers yet — they return no data until
implemented.

## Common Patterns

```python
# Alive and birth-verified
crvs.dci.is_alive == true and crvs.dci.birth_verified == true

# Any severe disability
dr.dci.vision_severe == true or dr.dci.hearing_severe == true or dr.dci.mobility_severe == true

# Same, with explicit thresholds
dr.dci.severity('Vision') >= 3 or dr.dci.severity('Hearing') >= 3

# Elderly OR disabled
age_years(me.birthdate) >= 60 or dr.dci.has_disability == true

# Child with verified birth
age_years(me.birthdate) < 18 and crvs.dci.birth_verified == true
```

## Troubleshooting

### Expression matches nobody

DCI variables only match registrants with a **fresh cached value**:

1. Is the variable linked to a **DCI-backed provider**? (Studio → Variables → External
   Source; the provider's DCI Integration tab must link a Data Source.)
2. Did you run **Sync DCI Values** for those registrants?
3. Has the value's **TTL expired**? Re-sync.
4. Inspect the cache: **Settings → Technical → CEL Domain → Data Management → Data
   Values**, filter by Variable Name (e.g. `crvs.dci.is_alive`).

### Some registrants never get a value

The sync resolves each registrant's identifier (UIN → DRN → national id → BRN, else
first available) and queries the registry with it. Registrants without an identifier —
or with one the registry doesn't know — are skipped. Check the Registrant IDs on the
person.

### Sync errors

- Check the DCI Data Source: **Test Connection**, OAuth2 credentials, state Active.
- Outbound calls are logged in the outgoing API log (`spp.api.outgoing.log`) with HTTP
  status and duration.
- One registrant's failure never aborts the batch — failures are logged and skipped.

### Compilation error mentions the accessor as a field

If an expression errors like `Invalid field res.partner.crvs`, the variable record for
that accessor is missing or inactive — the resolver could not recognize it. Verify the
variable exists and is active.

## Advanced

### Adding a new DCI metric

1. Add a fetch handler in `spp_dci_indicators/models/dci_cel_fetcher.py`
   (`_dci_metric_handlers` for simple metrics; `DCI_METHOD_ACCESSORS` +
   `_compute_method_values` for parameterized ones).
2. Add the `spp.cel.variable` record (external source type, `ttl` cache strategy, the
   `<registry>.dci.<metric>` accessor) in `data/indicator_data.xml`.
3. Link the variable to a DCI-backed provider and sync.

### How values are stored

Each synced value is one `spp.data.value` row keyed by
`(variable accessor, registrant, period, params)` with an `expires_at` computed from the
variable's TTL. Parameterized methods store one row per argument, keyed via
`params_hash`. CEL compiles the accessor into a SQL sub-query over this table.

## Support

- GitHub: https://github.com/OpenSPP/OpenSPP2
- Documentation: https://docs.openspp.org
- Community: https://openspp.org/community
