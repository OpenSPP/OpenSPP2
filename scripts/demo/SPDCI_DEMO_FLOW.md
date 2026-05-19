# OpenSPP DCI Demo Flow

---

## Pre-demo state (assumed before slide 1)

| Side         | State                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| SP           | Fresh database. Modules installed (`spp_dci_openspp_dr` + `spp_dci_openg2p`). 0 registrants. DR data source URL set.                             |
| DR           | `openspp_dr` database with 8 approved disability assessments seeded for `IND-NSR-0001/0003/0005/0007/0009/0011/0013/0015`. DCI bypass flags set. |
| OpenG2P SR   | Live at `partner-nsr.play.openg2p.org`. 15 personas seeded by OpenG2P. No SP-side action needed.                                                 |
| Demo program | "Disability Assistance" defined on SP. Eligibility rule: `has_disability == true && is_poor == "low"`.                                           |

Run `scripts/demo/reset_spdci_demo.py` to guarantee a clean
cache + draft memberships if you ran a dry run earlier.

---

## Scene 1 — Frame the problem (1 min, slide-only)

**Slide content**: the narrative paragraph from the briefing.

> A government runs a social-protection program — **Disability Assistance** — that
> targets registrants who are **both** living with a disability **and** classified as
> poor. The two facts live in two independent registries owned by two independent
> agencies. OpenSPP composes the eligibility decision by querying both over the DCI
> standard, in real time, with a single click.

**Talking points**

- Two registries, two owners, one decision.
- The hard problem isn't computing eligibility — it's federating data across independent
  agencies without replicating their records.
- SPDCI is the standard we use to do it without per-vendor glue.

**Transition**: "Let's see what the platform looks like before any of this is wired in."

---

## Scene 2 — The empty SP (1 min, live)

**On screen**: SP UI → Registry → Registrants list. Empty.

**Presenter does**: nothing yet. Just lets the audience see "0 registrants".

**Talking points**

- This is a clean OpenSPP install. We haven't pre-loaded data; we'll populate the
  registry the way an operator would in production.
- The SP doesn't know about the Social Registry's records yet. Names, identifiers,
  demographics — all live on the SR.
- We're going to pull a list of registrants from the SR using DCI search-sync, let the
  operator review them, and import the chosen ones.

**Transition**: "Watch how the operator pulls registrants from the Social Registry."

---

## Scene 3 — Import from the Social Registry (2 min, live)

**On screen**: SP UI → Registry → **Import from External Registry**.

**Presenter does**:

1. Click **Registry → Import from External Registry**.
2. Form opens. Note **Source Registry** is pre-filled with **Social Registry**.
   - _One sentence aside_: "That's the OpenG2P SR endpoint. It's just a DCI data source
     — production deployments configure their own."
3. Discovery mode: **Identifier range sweep** (the default).
4. Range: `IND-NSR-` `0001` to `0015`, pad `4`.
5. Auto-enroll: pick **Disability Assistance**.
6. Click **Preview**.

**On screen**: 15 preview rows fill in. Each row carries given_name, surname, sex,
birth_date pulled fresh from the SR over DCI.

**Talking points**

- Every row on the preview is the result of a separate DCI search-sync request to the
  live SR. The SR returned name + demographics + identifier metadata in the DCI standard
  envelope.
- The wizard captured **only the minimum**: name, sex, birth_date, UIN. The rich
  attributes (income_level, marital_status, employment_status) stay on the SR — we'll
  fetch them on demand at eligibility time.
- All 15 rows are pre-selected because none of them exist on the SP yet.
- If we re-ran the wizard, already-imported rows would show "already on SP" and be
  unchecked by default.

**Presenter does**: Click **Import Selected**.

**On screen**: "15 registrant(s) imported." Wizard closes; navigate back to Registrants
list to show the 15 new partners with their UIN reg_ids.

**Transition**: "Now the SP has identifiers. It doesn't yet have disability data or
poverty data. Let's run eligibility and watch the federation kick in."

---

## Scene 4 — The program and its CEL rule (1 min, live)

**On screen**: SP UI → Programs → **Disability Assistance**.

**Presenter does**: open the program form. Scroll to the eligibility rule.

**Slide content** (recap):

```
has_disability == true && is_poor == "low"
```

**Talking points**

- This is a **CEL** (Common Expression Language) rule. Google's open-source expression
  DSL. We use it because CEL is vendor-neutral and the operator can change a rule
  without touching code.
- `has_disability` and `is_poor` are CEL **variables**. Each one is bound to a registry
  behind the scenes:
  - `has_disability` → OpenSPP-DR (Disability Registry) over DCI
  - `is_poor` → OpenG2P SR (Social Registry) over DCI, reading `income_level`
- The operator doesn't see "Disability Registry" or "OpenG2P" in the rule. They see
  semantic names. Swapping the backing source is a configuration change, not a code
  change.
- The rule will evaluate true for any registrant who is both flagged as disabled by the
  DR _and_ classified `income_level == "low"` by the SR.

**Transition**: "One click."

---

## Scene 5 — Enroll Eligible (2 min, live, the centerpiece)

**On screen**: Disability Assistance program form, top bar showing membership counts (15
draft / 0 enrolled).

**Presenter does**: click **Enroll Eligible**.

**What audiences see**: a few seconds of work, then the count flips to **4 enrolled / 11
draft**.

**Talking points** (while it runs):

- Under the hood, the platform just fired **30 DCI requests** in parallel: 15 to the DR
  for `has_disability`, 15 to the SR for `is_poor`.
- Every response was cached in `spp.data.value` with a TTL.
- Every fetch was audited in `spp.dci.fetch.audit` for compliance.
- The CEL executor compiled the rule into a SQL query that AND-joined the two cached
  datasets to produce the final eligibility set.
- The whole thing took under five seconds in this demo. In production this is the
  bottleneck you'd tune with caching and async pre-fetch.

**On screen after**: the 4 enrolled — Alex Rivera, Morgan Cole, Taylor Brooks, Sam
Hayes. (Names match the briefing sheet's expected outcome.)

**Slide content** (split view recommended):

| Why these 4?                 | Each is in **both** registries with both predicates true |
| ---------------------------- | -------------------------------------------------------- |
| Alex Rivera (IND-NSR-0001)   | DR: has_disability=true • SR: income_level=low           |
| Morgan Cole (IND-NSR-0004)   | DR: has_disability=true • SR: income_level=low           |
| Taylor Brooks (IND-NSR-0010) | DR: has_disability=true • SR: income_level=low           |
| Sam Hayes (IND-NSR-0013)     | DR: has_disability=true • SR: income_level=low           |

**Transition**: "Let's see why one of them got picked — by drilling into the audit
trail."

---

## Scene 6 — Drill into one decision (2 min, live)

**On screen**: SP UI → click Alex Rivera in the enrolled list.

**Presenter does**: open Alex's partner form. Navigate to the audit log / DCI fetch
audit related list (depending on UI exposure, this may be via the developer menu or a
dedicated tab).

**Talking points**

- Each row here is a DCI fetch that contributed to Alex's eligibility. We see two: one
  to the DR for has_disability, one to the SR for is_poor.
- The audit row carries the message_id (the DCI envelope's identifier), the registry
  that answered, the timestamp, and the resolved value. We can reconstruct the exact
  wire conversation for compliance review months later.
- This is the "show your work" property of SPDCI: a federated eligibility decision is
  reproducible, attributable, and audit-ready.

**Optional**: open one row, show the envelope/message detail.

**Transition**: "And to prove these aren't synthetic numbers, let's see the same data on
the source registry."

---

## Scene 7 — Same record on the live SR (1 min, live)

**On screen**: terminal with a `curl` or browser tab to OpenG2P's playground.

**Presenter does**: run a one-line `curl` (or open the UI) against
`partner-nsr.play.openg2p.org`:

```bash
# Pre-canned with auth + envelope already filled in.
./scripts/demo/probe_openg2p.sh IND-NSR-0001
```

(If you don't have a pre-canned probe, fall back to the wizard's preview of
`IND-NSR-0001` — the same JSON travels over the wire.)

**On screen**: the SR's response showing the same Alex Rivera record with
`income_level: "low"` in `additional_attributes` or `reg_records[0]`.

**Talking points**

- Same identifier, same record, returned by an independent OpenG2P-hosted registry.
  We're not mocking anyone — this is a live, third-party endpoint.
- The DR side is our own OpenSPP instance acting as a DCI server. Different agency,
  different platform, both speaking the same protocol.

**Transition**: "Let's recap and look at what's interesting beyond the happy path."

---

## Scene 8 — Recap and what each failure mode tells us (1 min, slide)

**Slide content** (compact version of the briefing's verdict table):

| Failure mode   | Example          | What it shows                                                                              |
| -------------- | ---------------- | ------------------------------------------------------------------------------------------ |
| Income not low | Kim Lee (medium) | SR says "not poor enough" — DCI returned a value, rule rejected it                         |
| No DR record   | Priya Rivera     | DR returned not_found — variable resolved to null, rule rejected                           |
| Both fail      | Noah Rivera      | Two failed predicates — no enrollment, no PII pulled from either side beyond identity      |
| Empty income   | (several rows)   | SR returned a record but `income_level` was unset — treated as null, fails strict equality |

**Talking points**

- The interesting thing isn't the 4 enrolled — it's that the platform handled four
  different failure modes without bespoke code. Each is just "a CEL predicate evaluated
  false, in a specific way."
- This is what "configuration over code" looks like in practice: an operator changes the
  rule to `has_disability == true || is_poor == "low"` and 11 of the 15 enroll instead
  of 4. No deployment, no Python.

---

## Scene 9 — Architecture map (1 min, slide)

**Slide content**: the topology diagram from the briefing.

**Talking points**

- Three independent processes, two HTTP boundaries, one decision.
- The SP is the **client** for both registries — it doesn't host their data, it queries
  them on demand.
- DCI is the protocol that lets us bring on a third or fourth registry later (CRVS, IBR,
  MOSIP eSignet for ID verification) without rewriting the eligibility logic. New
  registry = new data source + new CEL variable; the rule grammar is unchanged.

---

## Scene 10 — Where this goes next (1 min, slide)

**Slide content**: three forward-looking bullets.

- **More registries**: CRVS for civil events, IBR for cross-program dedup, MOSIP eSignet
  for OIDC-based ID verification. All slot in via the same SPDCI bridge.
- **Async pre-warm**: long-running cohort scans move off the request path and into queue
  jobs, with operator-visible progress.
- **Configurable consent**: per-source consent purpose codes, signed by the SP's
  registered DCI sender key.

---

## If you only have 5 minutes (lightning version)

Drop scenes 2, 6, 7, 9, 10. Keep:

1. Scene 1 — Frame the problem
2. Scene 3 — Import from SR (skip the wizard internals, just show the final 15-row
   preview and import)
3. Scene 4 — The rule
4. Scene 5 — Enroll Eligible → 4 / 15
5. Scene 8 — The failure-mode table

---


