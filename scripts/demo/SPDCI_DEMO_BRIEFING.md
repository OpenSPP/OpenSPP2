# SPDCI Federated Demo — Briefing Sheet

A one-page reference for the live demo of OpenSPP V2's SPDCI federated-eligibility flow.

## The narrative

> A government runs a social-protection program — **Disability Assistance** — that targets registrants who are **both** living with a disability **and** classified as poor. The two facts live in two independent registries owned by two independent agencies. OpenSPP composes the eligibility decision by querying both over the DCI standard, in real time, with a single click.

## Demo eligibility rule

```
has_disability == true && is_poor == "low"
```

| Clause | Source registry | Resolved via |
|---|---|---|
| `has_disability` | **OpenSPP-DR** (Disability Registry, a sibling OpenSPP instance) | DCI `/dci_api/v1/disability/registry/sync/search` |
| `is_poor` | **OpenG2P SR** (National Social Registry, `partner-nsr.play.openg2p.org`) | DCI `/dci/registry/sync/search`, reads `income_level` |

Both fetches happen inside Enroll Eligible's pre-warm phase. The CEL executor ANDs the two SQL subqueries against the SP's cohort.

## The 15 demo registrants

Each persona on the SP carries a UIN reg_id matching an OpenG2P SR seed identifier (`IND-NSR-0001`..`IND-NSR-0015`). Names mirror OpenG2P's actual seed records so the federation story stays honest — operators can curl OpenG2P and verify the same name comes back.

| # | UIN | Registrant | OpenG2P `income_level` | OpenSPP-DR `has_disability` | Verdict |
|---|---|---|---|---|---|
| 1 | `IND-NSR-0001` | Alex Rivera | **low** | **true** | ✅ **ENROLLED** |
| 2 | `IND-NSR-0002` | Priya Rivera | low | false | not eligible (no DR record) |
| 3 | `IND-NSR-0003` | Noah Rivera | (empty) | false | not eligible (both fail) |
| 4 | `IND-NSR-0004` | Morgan Cole | **low** | **true** | ✅ **ENROLLED** |
| 5 | `IND-NSR-0005` | Leah Cole | low | false | not eligible (no DR record) |
| 6 | `IND-NSR-0006` | Nia Cole | (empty) | true | not eligible (income not low) |
| 7 | `IND-NSR-0007` | Kim Lee | medium | true | not eligible (income not low) |
| 8 | `IND-NSR-0008` | Jun Lee | medium | false | not eligible (both fail) |
| 9 | `IND-NSR-0009` | Rin Lee | (empty) | true | not eligible (income not low) |
| 10 | `IND-NSR-0010` | Taylor Brooks | **low** | **true** | ✅ **ENROLLED** |
| 11 | `IND-NSR-0011` | Iris Brooks | (empty) | false | not eligible (both fail) |
| 12 | `IND-NSR-0012` | Reyn Brooks | (empty) | false | not eligible (both fail) |
| 13 | `IND-NSR-0013` | Sam Hayes | **low** | **true** | ✅ **ENROLLED** |
| 14 | `IND-NSR-0014` | Dev Hayes | low | false | not eligible (no DR record) |
| 15 | `IND-NSR-0015` | Asha Hayes | (empty) | true | not eligible (income not low) |

**Expected outcome**: 4 / 15 enrolled. The other 11 illustrate each failure mode of the AND'd rule.

## Topology

```
                            ┌────────────────────────┐
                            │  OpenG2P SR (cloud)    │
                            │  partner-nsr           │
                            │  Returns income_level  │
                            └───────────▲────────────┘
                                        │ DCI search-sync
                                        │ (HTTPS, expression query)
┌──────────────────────┐   ┌────────────┴────────────┐   ┌──────────────────────┐
│  Operator clicks     │──▶│   OpenSPP SP instance   │──▶│  OpenSPP-DR instance │
│  "Enroll Eligible"   │   │   (./spp container)     │   │   (sibling container)│
│                      │   │                         │   │                      │
│  Program rule:       │   │ • spp_cel_dci_bridge    │   │ • spp_disability_    │
│  has_disability ==   │   │ • spp_dci_openg2p (SR)  │   │   registry           │
│   true &&            │   │ • spp_dci_openspp_dr    │   │ • spp_dci_server     │
│  is_poor == "low"    │   │   (DR client)           │   │ • spp_dci_server_    │
│                      │   │                         │   │   disability         │
└──────────────────────┘   └─────────────────────────┘   └──────────────────────┘
                                        │ DCI search-sync (HTTP, in-container network)
                                        ▼
                              http://openspp-dr:8069
```

The bridge fans the eligibility check out to two independent registries, caches the results in `spp.data.value`, audits every fetch in `spp.dci.fetch.audit`, and lets the CEL executor compose the final eligibility decision in one SQL query.

## Glossary

### Standards & protocols

**SPDCI** — Social Protection Digital Convergence Initiative. A community-driven effort under the broader DCI banner to standardise how social-protection MIS systems interoperate with identification, civil-registration, and other government registries.

**DCI** — Digital Convergence Initiative. The umbrella body publishing open standards for cross-registry data exchange, hosted at [spdci.org](https://spdci.org). The DCI specs define wire-level message envelopes, header conventions, signature/consent blocks, and per-registry search semantics.

**Search-Sync** — DCI's synchronous search protocol. A POST request carrying a DCI envelope (`signature`, `header`, `message.search_request`) returns matching registry records in the same HTTP response. Used for "tell me what you know about this person" lookups. Contrasted with search-async (a callback-based variant for long-running queries).

**OIDC / OAuth2** — The OpenID Connect / OAuth 2.0 family. Used for authentication and authorisation, especially with MOSIP eSignet. Different protocol from DCI search-sync: OIDC mediates **user authentication via browser redirect**; DCI does **server-to-server data lookup**.

### Registries

**SR — Social Registry**. Holds household-composition and socio-economic data used for eligibility targeting (e.g., `income_level`, `marital_status`, `employment_status`). In this demo, the SR is OpenG2P's playground at `partner-nsr.play.openg2p.org`. SPDCI registry-type code: `SR`.

**DR — Disability Registry**. Holds disability assessments and related data (e.g., `has_disability`, severity, review cadence). In this demo, the DR is a second OpenSPP instance running `spp_disability_registry` + `spp_dci_server_disability`. SPDCI registry-type code: `DR`.

**CRVS — Civil Registration and Vital Statistics**. Holds birth/death/marriage records. Not used in this demo. Code: `CRVS`.

**IBR — Integrated Beneficiary Registry**. Cross-program beneficiary index, often used to detect duplicate enrollment. Not used in this demo. Code: `IBR`.

**FR — Functional/Farmer Registry**. Domain-specific registries (e.g., farmer registries). Code: `FR`.

### CEL

**CEL — Common Expression Language**. Google's open-source domain-specific language for evaluating boolean and numeric expressions. OpenSPP uses CEL for program eligibility rules. Example:

```
has_disability == true && age_years(r.birthdate) >= 18
```

**CEL accessor** — The identifier inside a CEL rule that references a registrant attribute (e.g., `has_disability`, `is_poor`, `age_years`). Accessors are **vendor-neutral** by design — rewriting a rule to read from a different vendor's registry doesn't change the CEL surface, only the data-source configuration backing the accessor.

**`spp.cel.variable`** — The Odoo model that backs a CEL accessor. Carries the value type, source (`field` / `external` / `computed` / `aggregate`), provider link, cache strategy, and other metadata.

**`metric()` call** — How the CEL planner translates a registry-backed variable when evaluating. A rule like `has_disability == true` compiles to `metric('has_disability', me) == true` and the executor's SQL fast path turns that into an `('id', 'in', <SQL subquery>)` clause on `spp.data.value`.

### OpenSPP-side terminology

**`spp.dci.data.source`** — A configured DCI endpoint (host, path, auth, sender/receiver ids, vendor adapter). One per external registry.

**`spp.data.provider`** — The CEL framework's reference to a backing source. A DCI-backed provider has `dci_data_source_id` set.

**`spp.cel.dci.dispatcher`** — Bridge code that, for a CEL variable backed by a DCI source, routes the fetch to the right per-registry-type handler (`_handler_sr`, `_handler_dr`, etc.) which then delegates to a vendor service adapter.

**Vendor adapter** — Optional Python service class that absorbs vendor-specific request/response quirks. Examples in this demo: `OpenG2PSocialService` (handles OpenG2P's expression-query / consent-block shape), `OpenSPPDRService` (unwraps `data.reg_records[0]` correctly).

**`spp.data.value`** — Persistent cache of resolved variable values. Each row: `(subject_model, subject_id, variable_name, period_key, value_json, expires_at, ...)`.

**`spp.dci.fetch.audit`** — Compliance log of every DCI fetch. One row per subject per fetch, regardless of outcome (ok / not_found / error). Surfaces who queried what, when, with what response.

### Other systems (referenced but out of scope)

**MOSIP** — Modular Open Source Identity Platform. National identity system used by several governments. Future-work integration point for SPDCI; not in this demo.

**eSignet** — MOSIP's OIDC-compliant authentication service. Mediates user identity verification via browser redirect + KYC token. Different protocol family from DCI search-sync. Phase 4 roadmap item in ADR-024.

**OpenG2P** — Open-source social-protection platform. Provides the SR (`partner-nsr.play.openg2p.org`) used in this demo's federated eligibility flow.

## See Also

- ADR-023 — CEL ↔ DCI External Fetch Bridge
- ADR-024 — Federated DCI Demo Topology for SPDCI
- `docs/plans/SPP_DCI_FEDERATED_DEMO_PLAN.md` — implementation plan
- `scripts/demo/setup_spdci_demo.py` — seed script for the 15 demo personas
- `scripts/demo/reset_spdci_demo.py` — per-iteration reset (membership + cache)
