# How a CEL expression turns into two DCI calls

This is the technical walkthrough behind one click of **Enroll Eligible** on the Disability Assistance program, when the program's CEL rule is:

```
has_disability == true && is_poor == "low"
```

The journey: one operator click → two HTTP DCI requests against two independent registries → one ANDed eligibility decision per partner.

## The big picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  OPERATOR clicks "Enroll Eligible" on the Disability Assistance program  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  spp.program.membership.manager.default      │
            │  ._prepare_eligible_domain() runs            │   (1) Eligibility entry point
            └────────────────────────┬─────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  PRE-WARM:  bridge eagerly fetches every     │   (2) Pre-warm hook
            │  active DCI-backed CEL variable for cohort   │       in spp_cel_dci_bridge
            └────────────────────────┬─────────────────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                ▼                                         ▼
    ┌───────────────────────┐                ┌────────────────────────┐
    │  has_disability       │                │  is_poor               │
    │  registry_type=DR     │                │  registry_type=SR      │
    │  vendor=openspp       │                │  vendor=openg2p        │
    └──────────┬────────────┘                └───────────┬────────────┘
               │                                         │
               ▼ DCI search-sync                         ▼ DCI search-sync
    ┌───────────────────────┐                ┌────────────────────────┐
    │  OpenSPP-DR           │                │  OpenG2P SR            │
    │  /dci_api/v1/         │                │  /dci/registry/        │
    │   disability/registry │                │   sync/search          │
    │   /sync/search        │                │                        │
    │                       │                │  partner-nsr.play.     │
    │  Returns reg_record   │                │  openg2p.org           │
    │  {has_disability:bool}│                │                        │
    └──────────┬────────────┘                │  Returns reg_record    │
               │                             │  {income_level:string} │
               │                             └───────────┬────────────┘
               │                                         │
               ▼                                         ▼
    ┌────────────────────────────────────────────────────────────────┐
    │  spp.data.value cache rows written per partner per variable    │   (3) Cache write
    │  {"value": true}  /  {"value": "low"}  /  {"value": null} ...  │
    └────────────────────────────────┬───────────────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  CEL parser + translator                     │   (4) Plan build
            │  has_disability == true && is_poor == "low"  │
            │  → AND[MetricCompare, MetricCompare]         │
            └────────────────────────┬─────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  CEL executor                                │   (5) SQL fast path
            │  Each MetricCompare → SQL subquery against   │
            │  spp_data_value table; ANDed together        │
            └────────────────────────┬─────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  PostgreSQL evaluates the final domain in    │   (6) Final eligibility query
            │  one query — returns matching partner IDs    │
            └────────────────────────┬─────────────────────┘
                                     │
                                     ▼
            ┌──────────────────────────────────────────────┐
            │  spp.program.membership rows flip:           │   (7) Result
            │  matching → enrolled, others → not_eligible  │
            └──────────────────────────────────────────────┘
```

The audit log (`spp.dci.fetch.audit`) gets one row per partner per fetch — 30 rows total for the 15 demo personas. That's the compliance trail.

## Step-by-step

### Step 1 — Operator click reaches the eligibility manager

The Enroll-Eligible button invokes `spp.program.enroll_eligible_registrants()` on the program. That iterates each membership manager configured on the program (the default one for our demo) and asks each: "give me a domain that selects the eligible partners."

`spp_cel_dci_bridge` overrides the default manager's `_prepare_eligible_domain()` so that **before** the CEL filter compiles, the cache for every DCI-backed variable gets pre-warmed.

→ Code: `spp_cel_dci_bridge/models/eligibility_manager.py`

### Step 2 — Pre-warm pulls every active DCI variable

The bridge calls:

```python
cache_mgr.precompute_cached_variables(subject_ids, period_key="current", program_id=program.id)
```

`cache_mgr` is `spp.data.cache.manager`. Internally it:

1. Searches every `spp.cel.variable` where `active=True` and `cache_strategy ∈ {ttl, manual}` — that finds **both** `has_disability` and `is_poor` (and the inactive `has_dependent_under_school_age` is skipped).
2. For each variable, calls `_compute_variable_values(variable, subject_ids, ...)`.

The bridge overrides `_compute_variable_values`: when the variable has `source_type='external'` AND a DCI-backed provider, it delegates to `_compute_dci_values`.

→ Code: `spp_cel_dci_bridge/models/data_cache_manager.py`

**Important design point**: the pre-warm fetches *all* active variables, not just the ones the rule references. We trade extra registry round-trips for executor simplicity. For 15 partners × 2 variables = 30 DCI calls.

### Step 3 — The dispatcher picks the right handler

`_compute_dci_values` calls:

```python
dispatcher.fetch_values_for_variable(variable, subject_ids, period_key)
```

The dispatcher (`spp.cel.dci.dispatcher`) looks at the variable's data-source `registry_type` and chooses a handler:

| `registry_type` | Handler in the bridge | Vendor override called if `vendor=...` is set |
|---|---|---|
| `DR` | `_handler_dr` | `OpenSPPDRService` (`vendor=openspp`) |
| `SR` | `_handler_sr` | `OpenG2PSocialService` (`vendor=openg2p`) |
| `CRVS`, `IBR`, `FR` | (registry-specific handlers; not used in this demo) | — |

Vendor adapters absorb per-vendor request/response quirks. OpenG2P needs a specific expression-query envelope shape with consent/authorize blocks; OpenSPP-DR speaks vanilla SPDCI.

→ Code: `spp_cel_dci_bridge/models/dci_dispatcher.py`,
  `spp_dci_openspp_dr/models/dci_dispatcher.py`,
  `spp_dci_openg2p/models/dci_dispatcher.py`

### Step 4 — Each handler builds and sends a DCI envelope

**For `has_disability` (DR side)**, `OpenSPPDRService.get_partner_record(partner)`:

1. Reads the partner's UIN from `spp.registry.id` (priority: UIN > DRN > NATIONAL_ID > NID).
2. Calls `DCIClient.search_by_id(identifier_type='UIN', identifier_value='IND-NSR-0001', ...)`.
3. Underneath, the DCI client POSTs a signed DCI envelope to the configured base URL + search endpoint.

The on-the-wire request is:

```
POST http://openspp-dr:8069/dci_api/v1/disability/registry/sync/search
Content-Type: application/json

{
  "signature": "",
  "header": {
    "version": "1.0.0",
    "message_id": "<uuid>",
    "message_ts": "2026-05-15T...",
    "action": "search",
    "sender_id": "openspp-sp.demo",
    "receiver_id": "openspp-dr.demo",
    "total_count": 1,
    "is_msg_encrypted": false
  },
  "message": {
    "transaction_id": "<uuid>",
    "search_request": [{
      "reference_id": "<uuid>",
      "timestamp": "2026-05-15T...",
      "search_criteria": {
        "reg_type": "ns:org:RegistryType:DR",
        "query_type": "idtype-value",
        "query": {"type": "UIN", "value": "IND-NSR-0001"}
      }
    }]
  }
}
```

**For `is_poor` (SR side)**, `OpenG2PSocialService.get_partner_record(partner)` does the same shape but with OpenG2P's expression-query format:

```
POST https://partner-nsr.play.openg2p.org/dci/registry/sync/search

{
  "signature": "",
  "header": { ...openspp-sp.demo → openg2p.demo... },
  "message": {
    "search_request": [{
      "search_criteria": {
        "reg_type": "Individual",
        "reg_record_type": "Individual",
        "query_type": "expression",
        "query": {
          "type": "ns:org:QueryType:expression",
          "value": {"expression": {"query": {"search_text": {"$eq": "IND-NSR-0001"}}}}
        },
        "consent": {"@context": "...", "@type": "Consent", ...},
        "authorize": {"@context": "...", "@type": "Authorize", ...}
      }
    }]
  }
}
```

The differences (consent block, expression-query shape, "Individual" literal reg_type) are exactly why `spp_dci_openg2p` has a vendor adapter and `spp_dci_openspp_dr` does not.

→ Code: `spp_dci_openspp_dr/services/openspp_dr_service.py`,
  `spp_dci_openg2p/services/openg2p_social_service.py`,
  `spp_dci_openg2p/services/openg2p_dci_client.py` (the envelope shaper)

### Step 5 — The remote registries answer

**OpenSPP-DR** (our own server module, `spp_dci_server_disability`):

1. FastAPI router at `/dci_api/v1/disability/registry/sync/search` receives the envelope.
2. Signature + bearer middleware validates the sender (dev-mode bypasses for the demo).
3. `DisabilitySearchService.execute_search()` extracts the UIN, looks up `spp.registry.id.value`, finds the matching partner.
4. Reads `partner.has_disability` (Boolean, computed by `spp_disability_registry` from the latest approved `spp.disability.assessment`).
5. Builds a response envelope with `data.reg_records[0] = {has_disability: true, ...}` and returns 200.

**OpenG2P SR** (their hosted service): receives the envelope, runs its expression query against its data store, returns `data.reg_records[0]` with `income_level`, `marital_status`, `occupation`, etc.

→ Code: `spp_dci_server_disability/routers/disability_router.py`,
  `spp_dci_server_disability/services/disability_search_service.py`

### Step 6 — Service unwraps response, dispatcher extracts the value

Back on the SP side, each service unwraps `message.search_response[0].data.reg_records[0]` and returns the raw record dict. The dispatcher then applies `variable.dci_attribute_path`:

- For `has_disability`, path = `has_disability` → extracts the Boolean True.
- For `is_poor`, path = `income_level` → extracts the string `"low"`.

The dispatcher writes a `spp.dci.fetch.audit` row capturing the result (`ok` / `not_found` / `error`), elapsed time, sender, variable, subject. Audit closure = compliance.

→ Code: `spp_cel_dci_bridge/models/dci_dispatcher.py`

### Step 7 — Cache write

The parent `data_evaluator` upserts a `spp.data.value` row for each (variable, subject_id):

```
variable_name  | subject_id | value_json           | expires_at
---------------+------------+----------------------+-----------
has_disability | 18         | {"value": true}      | now+300s
is_poor        | 18         | {"value": "low"}     | now+300s
```

15 partners × 2 variables = 30 rows after pre-warm. With `cache_strategy='ttl'` and `cache_ttl_seconds=300`, the rows are good for 5 minutes — subsequent eligibility checks in that window skip the DCI calls.

→ Code: `spp_cel_domain/models/data_evaluator.py:precompute_cached_variables`

### Step 8 — CEL parsing → plan

The CEL string is parsed by `spp.cel.parser`:

```
"has_disability == true && is_poor == "low""
              │
              ▼  tokenize + parse
Compare(Compare(Call(metric('has_disability', me)), ==, Literal(True)),
        AND,
        Compare(Call(metric('is_poor', me)), ==, Literal('low')))
              │
              ▼  translator
AND[ MetricCompare(metric='has_disability', op='==', rhs=True),
     MetricCompare(metric='is_poor',        op='==', rhs='low') ]
```

The translator picked `MetricCompare` nodes because each side calls `metric('<name>', me)` — a registry-backed variable lookup.

→ Code: `spp_cel_domain/services/cel_parser.py`,
  `spp_cel_domain/models/cel_translator.py`,
  `spp_cel_domain/models/cel_queryplan.py`

### Step 9 — Executor builds SQL subqueries

The executor (`spp.cel.executor`) walks the plan. For each `MetricCompare`, when the cache is fresh AND the comparison is supported, it builds an SQL fast-path subquery:

```sql
-- For has_disability == true:
SELECT DISTINCT fv.subject_id
FROM spp_data_value fv
WHERE fv.variable_name = 'has_disability'
  AND fv.subject_model = 'res.partner'
  AND fv.period_key = 'current'
  AND fv.error_code IS NULL
  AND (fv.expires_at IS NULL OR fv.expires_at > NOW())
  AND (CASE WHEN jsonb_typeof(fv.value_json) = 'object'
            THEN (fv.value_json -> 'value')::boolean
       END) = true
```

And similarly for `is_poor == 'low'` (string cast via `value_json ->> 'value'`).

Each subquery becomes an Odoo domain clause `('id', 'in', <SQL subquery>)` and gets ANDed onto the final domain by the executor's top-level composer (this is the AND-of-overrides fix from commit `503e7fd7`).

→ Code: `spp_cel_domain/models/cel_executor.py` — see `_metric_inselect_sql` for the SQL build and the top-level `compile_and_preview` for the AND composition.

### Step 10 — One Odoo query, one PostgreSQL roundtrip

The final domain handed to `res.partner.search()` looks like:

```python
[
    ('is_registrant', '=', True),
    ('is_group', '=', False),
    ('id', 'in', [18, 19, 20, ..., 32]),     # cohort restriction
    ('disabled', '=', False),
    ('id', 'in', <SQL subquery for has_disability=true>),
    ('id', 'in', <SQL subquery for is_poor='low'>),
]
```

Odoo turns this into one big SQL with two subselects ANDed in the WHERE. PostgreSQL evaluates it once. Result: 4 matching partner IDs — Alex, Morgan, Taylor, Sam.

### Step 11 — Memberships flip

The eligibility manager writes each partner's `spp.program.membership.state`:
- 4 matching partners → `enrolled`
- 11 non-matching → `not_eligible`

In the UI, the Programs Membership list reflects the new states.

## Why this matters for the SPDCI story

A few things to highlight in the presentation:

1. **No registry holds all the data.** The eligibility decision needs disability data (DR) AND poverty data (SR). Each registry owns what it's authoritative for — neither leaks data into the other. This is the federated principle.

2. **The CEL surface is vendor-neutral.** The rule reads `has_disability == true && is_poor == "low"` — no mention of OpenG2P, OpenSPP-DR, OAuth, or HTTP. Swap OpenG2P out for a national SR; the rule doesn't change. Configuration adjustments only.

3. **One operator click triggers two DCI calls per partner.** 15 partners × 2 variables = 30 round-trips, all in parallel cohort batches. Pre-warmed once, cached for 5 minutes, the same cohort can be re-evaluated repeatedly without re-querying.

4. **The audit trail captures every fetch.** `spp.dci.fetch.audit` records 30 rows per click — variable, sender, receiver, subject, outcome, elapsed time. This is the compliance evidence that "we asked the DR for X and got Y at time T."

5. **PostgreSQL composes the final decision.** Once the cache is warm, eligibility is a single SQL query over local data — no extra round-trips, scales to millions of partners. The SPDCI step is the fetch; the composition is local.

## Try it during the demo

```bash
# Reset state (drafts + cache flush)
docker compose exec openspp-dev odoo shell -d openspp --no-http \
  < scripts/demo/reset_spdci_demo.py

# Click Enroll Eligible in the UI.
# Watch the live log:
docker compose logs -f openspp-dev | grep -E "CEL|DCI|Pre-comput|Pre-warm"

# In the UI:  Programs → Disability Assistance → Memberships
#   See 4 Enrolled, 11 Not Eligible.
# In the UI:  DCI → Fetch Audit
#   See 30 rows (15 partners × 2 variables), each with provider, subject, result, elapsed_ms.

# Verify the cached values directly:
docker compose exec db psql -U odoo -d openspp -c \
  "SELECT subject_id, variable_name, value_json
   FROM spp_data_value
   WHERE variable_name IN ('has_disability', 'is_poor')
   ORDER BY subject_id, variable_name;"
```

That's the complete journey from CEL syntax to two federated DCI calls to one eligibility decision.
