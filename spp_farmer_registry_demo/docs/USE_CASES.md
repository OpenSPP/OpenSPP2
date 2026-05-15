# Farmer Registry Demo — Use cases

> **Locale note:** The reference data shipped with this demo is coded against `ph_PH`
> (Philippine names, currency, area codes, bank list, place names). The structure of the
> use cases — stories, scenarios, roles, geographic dimension — is locale-agnostic and
> can be re-keyed to any country profile by swapping the persona names in
> `farmer_blueprints.py`, the area codes / GPS in the `STORY_FARMS` table, and the bank
> list referenced in the demo generator. Place names in the prose below ("Cabanatuan",
> "Cotabato City", etc.) are illustrative; the underlying steps apply to any equivalent
> regional centre / rural area pair.

## Demo users

The demo install seeds the following user accounts. All passwords are `demo` unless
noted otherwise. Use these to exercise role-gated views, approval flows, and the CR
validator chain.

| Login                | Password | Role(s)                         | Used in scenarios                              |
| -------------------- | -------- | ------------------------------- | ---------------------------------------------- |
| `admin`              | `admin`  | System Administrator (built-in) | Any — full access                              |
| `demo_manager`       | `demo`   | Farm Manager + CR Requestor     | Program lifecycle, CR submission, dashboards   |
| `demo_officer`       | `demo`   | Farm User + CR Requestor        | Farm data entry, CR submission                 |
| `demo_supervisor`    | `demo`   | Farm Manager                    | Program manager view, approvals                |
| `demo_viewer`        | `demo`   | Farm User                       | Read-only walkthroughs                         |
| `cr_local_validator` | `demo`   | CR Local Validator (Tier-1)     | Local CR approval / revision-request scenarios |
| `cr_hq_validator`    | `demo`   | CR HQ Validator (Tier-2)        | HQ-tier CR approval scenarios                  |

## Farm stories

Each farm is named by its family name and identified by an FM-code (FM1–FM8). Programs
that target groups enroll the farm — not individual members. Multi-program enrollment is
allowed when the farm satisfies more than one program's CEL.

### Story 1: FM1 — Smallholder rice farmer, full lifecycle to graduation

**Demonstration purpose:** End-to-end Input Subsidy lifecycle — enrolled, paid through
three cycles, then graduated. Contrasts with FM2 who stays multi-enrolled and FM3 who
continues active. Primary story for "graduation after target met".

**Program(s) the farm is enrolled in:**

| Program       | Reason for eligibility                        | Compliance                                           | Status                 |
| ------------- | --------------------------------------------- | ---------------------------------------------------- | ---------------------- |
| Input Subsidy | smallholder (2.0 ha ≤ 5), has productive land | **Passed** each cycle — productive land share ≥ 50 % | **Exited** (graduated) |

**Farm journey:**

1. Enrolled in Input Subsidy 150 days ago (rice, 2.0 ha, Cabanatuan area)
2. Payment #1 (₱200) — paid 120 days ago
3. Payment #2 (₱200) — paid 90 days ago
4. Payment #3 (₱200) — paid 60 days ago
5. Compliance pass each cycle (productive land = 100 % of total)
6. **Graduated 30 days ago** — target met, exited program

**Existing change requests for the farm:**

- `update_farm_details` (approved) — Farm expanded to 3.0 ha after acquiring adjacent
  parcel

**Farm assets:** 1 hand tractor (machinery, operational) attached to the main land
parcel.

**Activity vocabulary:** Rice cultivation references the FAO ICC 1.1 crop code `0116`
(Rice, paddy) — the same standard used by national agricultural censuses.

**Geographical location:** Inland rice plains — Cabanatuan, Nueva Ecija

---

### Story 2: FM2 — Multi-program mixed farmer

**Demonstration purpose:** A farm that satisfies more than one program's CEL
simultaneously. Demonstrates concurrent enrollment, separate cycle/payment streams, and
multi-CR sequencing on the same farm. Primary story for "multi-program coordination".

**Program(s) the farm is enrolled in:**

| Program           | Reason for eligibility                                        | Compliance                                   | Status   |
| ----------------- | ------------------------------------------------------------- | -------------------------------------------- | -------- |
| Input Subsidy     | smallholder (3.0 ha), has productive land (rice + vegetables) | **Passed** — productive land = 67 % of total | Enrolled |
| Livestock Support | livestock_count = 50 (chickens) > 0                           | N/A (no compliance on this program)          | Enrolled |

**Farm journey:**

1. Enrolled in Input Subsidy 100 days ago (mixed farm: 1.5 ha rice + 0.5 ha vegetables +
   50 chickens)
2. Payment #1 — Input Subsidy ₱250 — paid 70 days ago
3. Payment #2 — Input Subsidy ₱250 — paid 40 days ago
4. Enrolled in Livestock Support 80 days ago (chickens = 50 heads)
5. Payment #1 — Livestock Support ₱275 — paid 50 days ago
6. Both enrollments still active

**Existing change requests for the farm:**

- `update_farm_details` (applied) — Expanded to 4.0 ha, added livestock area
- `manage_farm_activity` (pending) — Register new chicken-rearing activity (50 heads,
  subsistence)

**Geographical location:** Inland mixed farming — San Pablo City, Laguna

---

### Story 3: FM3 — Senior livestock farmer, gender + age diversity

**Demonstration purpose:** A senior female farmer whose primary income is livestock.
Demonstrates non-cash-crop targeting and the per-head benefit formula. Contrasts with
FM1's flat per-hectare payment.

**Program(s) the farm is enrolled in:**

| Program           | Reason for eligibility           | Compliance                          | Status   |
| ----------------- | -------------------------------- | ----------------------------------- | -------- |
| Livestock Support | livestock_count = 20 (goats) > 0 | N/A (no compliance on this program) | Enrolled |

**Farm journey:**

1. Enrolled in Livestock Support 120 days ago (mixed farm: 0.5 ha crops + 20 goats, 1.0
   ha total)
2. Payment #1 — ₱275 (livestock_base 75 + 20 heads × ₱10) — paid 90 days ago
3. Payment #2 — ₱275 — paid 60 days ago
4. Payment #3 — ₱275 — paid 30 days ago
5. Active enrollment, not yet graduated

**Existing change requests for the farm:**

- `update_farm_details` (approved) — Land tenure transferred to owner after inheritance

**Geographical location:** Inland plateau, livestock area — Lipa City, Batangas

---

### Story 4: FM4 — Climate-vulnerable farmer with idle land

**Demonstration purpose:** A farmer whose declared idle land triggers Climate Resilience
eligibility. Demonstrates the program's targeting logic (`farm_size_idle > 0`) and BARMM
conflict-affected context. Contrasts with FM1/FM2 who satisfy productive-land programs
only.

**Program(s) the farm is enrolled in:**

| Program            | Reason for eligibility                            | Compliance                          | Status   |
| ------------------ | ------------------------------------------------- | ----------------------------------- | -------- |
| Climate Resilience | smallholder (4.0 ha), farm_size_idle = 1.0 ha > 0 | N/A (no compliance on this program) | Enrolled |

**Farm journey:**

1. Enrolled in Climate Resilience 55 days ago (vulnerability: very_high; 3.0 ha rice +
   1.0 ha idle/fallow)
2. Payment #1 — ₱200 — paid 50 days ago
3. Payment #2 — ₱200 — paid 35 days ago
4. Active enrollment

**Existing change requests for the farm:**

- `update_farm_details` (rejected) — Request to reclassify productive area (1.5 ha
  crops, 2.5 ha idle); rejected pending field verification

**Irrigation infrastructure** (anchors Scenario 10):

| Asset                         | Type      | Capacity             | Status                               | Network role                         |
| ----------------------------- | --------- | -------------------- | ------------------------------------ | ------------------------------------ |
| Cotabato Irrigation Reservoir | Reservoir | 5 000 m³ effective   | Reduced (design ≈ 15 000 m³, silted) | Source for the canal branch          |
| Cotabato Main Canal Branch    | Canal     | 300 m³ flow capacity | Carrying reduced flow                | Sourced by the reservoir; serves FM4 |

The reduced upstream capacity is the narrative explanation for FM4's 1 ha of idle/fallow
land — it's not random non-cultivation, it's the downstream consequence of a degraded
irrigation network.

**Land parcel:** A polygon (≈ 4 ha total area, of which 1 ha idle) is plotted at
Cotabato City and exportable as GeoJSON via `spp.land.record.get_geojson()`.

**Geographical location:** Inland BARMM — Cotabato City, Maguindanao

---

### Story 5: FM5 — Young female farmer, organic transition

**Demonstration purpose:** Young female farmer in the highlands transitioning toward
organic agriculture. Demonstrates the diversity dimension and Logic Pack–driven
eligibility for early-career smallholders.

**Program(s) the farm is enrolled in:**

| Program       | Reason for eligibility                    | Compliance                                    | Status   |
| ------------- | ----------------------------------------- | --------------------------------------------- | -------- |
| Input Subsidy | smallholder (2.0 ha), has productive land | **Passed** — productive land = 100 % of total | Enrolled |

**Farm journey:**

1. Enrolled in Input Subsidy 70 days ago (vegetables + maize, 2.0 ha)
2. Payment #1 — ₱200 — paid 45 days ago
3. Active enrollment

**Existing change requests for the farm:**

- `manage_farm_activity` (draft) — Register organic vegetable cultivation (commercial,
  0.5 ha)

**Geographical location:** Mountain valley highlands — La Trinidad, Benguet

---

### Story 6: FM6 — Aquaculture, non-crop farming

**Demonstration purpose:** Demonstrates that the registry handles non-crop farming. The
farm is enrolled in Aquaculture Support — a program that targets a single field
(`aquaculture_count > 0`) ignored by every other program.

**Program(s) the farm is enrolled in:**

| Program             | Reason for eligibility          | Compliance                          | Status   |
| ------------------- | ------------------------------- | ----------------------------------- | -------- |
| Aquaculture Support | aquaculture_count > 0 (tilapia) | N/A (no compliance on this program) | Enrolled |

**Farm journey:**

1. Enrolled in Aquaculture Support 90 days ago (0.5 ha tilapia fishpond)
2. Payment #1 — ₱250 — paid 60 days ago
3. Payment #2 — ₱250 — paid 30 days ago
4. Active enrollment

**Existing change requests for the farm:**

- `manage_farm_activity` (pending) — Update tilapia production (3,500 kg current, 4,000
  kg expected)

**Geographical location:** Inland fishpond area — Dagupan, Pangasinan

---

### Story 7: FM7 — Equipment Grant + Input Subsidy stack

**Demonstration purpose:** Young but experienced female farmer in BARMM. Qualifies for
both Input Subsidy and Equipment Grant (12 years' experience clears the
`experience_years >= 2` threshold). Demonstrates BARMM women in agriculture.

**Program(s) the farm is enrolled in:**

| Program         | Reason for eligibility                    | Compliance                                                | Status   |
| --------------- | ----------------------------------------- | --------------------------------------------------------- | -------- |
| Input Subsidy   | smallholder (1.5 ha), has productive land | **Passed** — productive land = 100 % of total             | Enrolled |
| Equipment Grant | smallholder, experience_years 12 ≥ 2      | **Passed** — still smallholder, still has productive land | Enrolled |

**Farm journey:**

1. Enrolled in Input Subsidy 130 days ago (rice + vegetables, 1.5 ha)
2. Payment #1 — Input Subsidy ₱175 — paid 100 days ago
3. Payment #2 — Input Subsidy ₱175 — paid 70 days ago
4. Enrolled in Equipment Grant 60 days ago
5. Payment #1 — Equipment Grant ₱500 — paid 30 days ago
6. Both enrollments active

**Existing change requests for the farm:**

- `manage_farm_activity` (approved) — Register new maize cultivation for dry season
  (commercial, 0.8 ha)

**Geographical location:** Inland BARMM — Marawi, Lanao del Sur

---

### Story 8: FM8 — Threshold edge case at the smallholder boundary

**Demonstration purpose:** Boundary-condition testing. The farm sits at the smallholder
threshold (5.0 ha) with deep diversification. Demonstrates that the eligibility CEL
evaluates correctly at the exact boundary and that highly experienced farmers (25 years)
still qualify when other criteria fit.

**Program(s) the farm is enrolled in:**

| Program           | Reason for eligibility                          | Compliance                          | Status   |
| ----------------- | ----------------------------------------------- | ----------------------------------- | -------- |
| Livestock Support | livestock_count = 45 (15 cattle + 30 goats) > 0 | N/A (no compliance on this program) | Enrolled |

**Farm journey:**

1. Enrolled in Livestock Support 180 days ago (3.0 ha crops + 2.0 ha livestock; 15
   cattle + 30 goats)
2. Payment #1 — ₱275 + per-head bonus — paid 150 days ago
3. Payment #2 — ₱275 — paid 120 days ago
4. Active enrollment, sitting exactly at smallholder boundary

**Existing change requests for the farm:**

- `update_farm_details` (revision) — Update experience years (claimed 20) and land
  breakdown; revision requested for supporting documents
- `manage_farm_asset` (pending) — Register additional water pump for irrigation
  expansion

**Farm assets:** 1 water pump (machinery, operational) attached to the main land parcel.

**Geographical location:** Inland highland plateau — Malaybalay, Bukidnon

---

## Edge case stories

These three farms exist to demonstrate eligibility _rejection_ paths. They are
referenced by the rejection demo scenario; they are not enrolled in any program.

### Story 9: EC1 — Large commercial farm

**Demonstration purpose:** A 50 ha commercial operation. Fails the `is_smallholder`
check (smallholder threshold = 5 ha) so it's rejected from Input Subsidy, Equipment
Grant, and Climate Resilience. Demonstrates targeting exclusion at the upper bound.

**Geographical location:** Background story — outside the smallholder envelope.

---

### Story 10: EC2 — Idle-land farm with no productive land

**Demonstration purpose:** A 3 ha farm where every hectare is idle. Fails
`has_productive_land` (Input Subsidy compliance also fails on the same field).
Demonstrates the difference between _having land_ and _having productive land_. Eligible
only for Climate Resilience because that program's CEL keys on `farm_size_idle > 0`.

**Geographical location:** Background story — climate-affected zone.

---

### Story 11: EC3 — New farmer, less than two years' experience

**Demonstration purpose:** A 2 ha farm with one year of experience. Eligible for Input
Subsidy (the CEL ignores experience) but rejected from Equipment Grant (requires
`experience_years >= 2`). Demonstrates the experience-based threshold.

**Geographical location:** Background story — eligible-with-caveats.

---

## Cooperative stories

Cooperatives in the demo are _groups of farms_ — true group-of-groups hierarchy. They
demonstrate that the registry supports federation structures and aggregated metrics over
member farms.

### Story 12: COOP1 — Nueva Ecija Rice Cooperative

**Demonstration purpose:** A two-farm rice cooperative spanning Central Luzon.
Aggregated farm size = 4.0 ha; combined eligibility behaves as the union of member-farm
CELs. Demonstrates the group-of-groups data model and cooperative-level reporting
(combined hectarage, member count).

**Member farms:** FM1 (Maria Santos, Nueva Ecija) + FM5 (Sofia Martinez, Benguet).

**Geographical location:** Central Luzon (Nueva Ecija, Benguet).

---

### Story 13: COOP2 — BARMM Farmers Federation

**Demonstration purpose:** A regional federation pooling two BARMM smallholder farms.
Combined size 5.5 ha — _exceeds_ the smallholder threshold individually. Demonstrates
that program eligibility is computed per _member_ farm, not on the federation aggregate
(so each member is still treated as a smallholder).

**Member farms:** FM4 (Amir Mangudadatu, Maguindanao) + FM7 (Sittie Pangandaman, Lanao
del Sur).

**Geographical location:** BARMM (Maguindanao, Lanao del Sur).

---

## Demo scenarios

### Scenario 1: New enrollment

Walk through enrolling a previously unregistered smallholder.

1. Open Registry → Vocabularies → Manage Vocabularies and confirm the FAO-aligned
   vocabularies are loaded — `urn:fao:icc:1.1` (crops), `urn:fao:livestock:2020`
   (livestock), `urn:fao:asfis:2024` (aquaculture). These back the species pickers used
   in step 5 below.
2. Open Settings → Farmer Registry → Seasons. The list shows three points of the
   `spp.farm.season` state machine: a `closed` prior-year season, an `active`
   current-year season, and (optionally) a `draft` future season the user can transition
   by hand. Activities can only be entered against an active season.
3. Open Registry → Groups → New, set `is_group=true` and `is_farm=true`
4. Add the head member and key fields (farm_total_size, farm_size_under_crops,
   experience_years)
5. Add a crop activity for the new farm. The species picker is backed by the FAO ICC 1.1
   vocabulary — pick `0116` Rice, paddy (matching FM1) or `0115` Maize, white (matching
   FM4). For aquaculture, the picker uses FAO ASFIS — pick `TIL` Tilapia (matching FM6).
6. Open Programs → Input Subsidy → Verify Eligibility
7. The new farm is moved from `not_eligible` (or absent) to `enrolled` because the CEL
   now matches
8. Show the resulting cycle and the first scheduled payment

**Key messages:**

- Eligibility is data-driven; changing the farm's facts changes the verdict
- The CEL evaluates on demand (Verify Eligibility) and at every cycle creation
- Activity classification uses FAO standards (ICC 1.1 / livestock 2020 / ASFIS)
  end-to-end — no free-text species fields, no national-only codes

---

### Scenario 2: Multi-program coordination

Show how a single farm fans out into two programs.

1. Open FM2 farm → see two memberships (Input Subsidy + Livestock Support)
2. Open Input Subsidy → Cycles → see FM2 in cycle 4
3. Open Livestock Support → Cycles → see FM2 in cycle 3 with a different payment amount
4. Show that the two payment streams are independent (separate batches, separate
   journals)

**Key messages:**

- Multi-program is a property of _fact pattern_, not configuration
- Each program owns its own cycle/entitlement workflow

---

### Scenario 3: Compliance failure and graduation

Use FM1 to demonstrate that a smallholder who keeps their productive land remains
compliant; contrast with a hypothetical farm that abandons its productive land.

1. Open Input Subsidy → compliance manager → show CEL
   `has_productive_land == true and farm_size_hectares > 0`
2. Open FM1 → cycle membership history → state `enrolled` for cycles 1–3, then
   `graduated`
3. Open a hypothetical FM-NULL with `farm_size_under_crops = 0` post-cycle → state
   `non_compliant` for that cycle, no entitlement generated

**Key messages:**

- Eligibility gates _enrollment_; compliance gates _each cycle's payment_
- Compliance can fire on any field reachable from CEL; here we use the productive-land
  share

---

### Scenario 4: Aquaculture targeting

Demonstrate that the system handles non-crop farming.

1. Open FM6 farm → activities → 0.5 ha tilapia fishpond
2. Open Aquaculture Support program → CEL `aquaculture_count > 0`
3. Open the program's cycle → FM6 in cycle 4 with payment ₱250
4. Verify Eligibility on FM1 (rice) — no change (FM1 is not eligible because
   `aquaculture_count == 0`)

**Key messages:**

- Programs can target specific livelihood types via CEL
- The same farm record carries multiple livelihoods (mixed farms enroll into multiple
  programs, single-livelihood farms into one)

---

### Scenario 5: Climate Resilience for idle land

Show how `farm_size_idle` becomes a positive signal for climate-vulnerable households.

1. Open Climate Resilience program → CEL `is_smallholder and farm_size_idle > 0`
2. Open FM4 → 3 ha rice + 1 ha idle = 4 ha total → matches CEL
3. Show the cycle and 2 paid payments (₱200 each)
4. Contrast with EC1 (50 ha, idle) → fails `is_smallholder` even though
   `farm_size_idle > 0`

**Key messages:**

- Idle land isn't always a negative — Climate Resilience treats it as a vulnerability
  signal
- CEL composition (AND) eliminates large commercial farms from a program targeting
  smallholders

---

### Scenario 6: Eligibility rejection paths

Show that the engine correctly excludes farms that look eligible at a glance.

1. EC1 (50 ha commercial) → rejected from Input Subsidy / Equipment Grant / Climate
   Resilience (fails `is_smallholder`)
2. EC2 (3 ha all idle) → rejected from Input Subsidy (fails `has_productive_land`)
3. EC3 (2 ha, 1 year experience) → eligible for Input Subsidy; rejected from Equipment
   Grant (fails `experience_years >= 2`)

**Key messages:**

- Each program's CEL is independent — rejecting one doesn't reject all
- Edge cases drive the test matrix; volume seeding produces farms across the same
  boundaries

---

### Scenario 7: Cooperative as group of groups

Demonstrate the group-of-groups data model.

1. Open COOP1 (Nueva Ecija Rice Cooperative) → see member farms FM1 + FM5
2. Show aggregated metrics — combined 4.0 ha, 2 member farms
3. Open FM1 → see cooperative membership (FM1 belongs to COOP1)
4. Run Verify Eligibility on Input Subsidy — eligibility is computed per member farm;
   the cooperative itself is not a program target

**Key messages:**

- Cooperatives are organisational records; programs target the underlying farms
- Federations can pool farms from different provinces/regions; the registry preserves
  the geographic data of each member

---

### Scenario 8: Change request lifecycle

Walk through the 10 demo CRs to show every CR state.

1. Approved: FM1 `update_farm_details` — farm expanded after acquisition
2. Applied: FM2 `update_farm_details` — added livestock area, applied automatically
3. Pending: FM2 `manage_farm_activity` — register chicken activity (awaiting validator)
4. Approved: FM3 `update_farm_details` — land tenure transfer
5. Draft: FM5 `manage_farm_activity` — register organic crop (UI workflow stage)
6. Pending: FM6 `manage_farm_activity` — update tilapia yield
7. Rejected: FM4 `update_farm_details` — reclassify idle land, rejected pending
   verification
8. Approved: FM7 `manage_farm_activity` — register dry-season maize
9. Revision: FM8 `update_farm_details` — experience claim flagged for documentation
10. Pending: FM8 `manage_farm_asset` — register additional water pump for irrigation
    expansion

**Key messages:**

- The demo covers 6 CR states (Draft, Pending, Approved, Applied, Rejected, Revision)
- Three CR types in scope (`update_farm_details`, `manage_farm_activity`,
  `manage_farm_asset`); the remaining type shipped by `spp_farmer_registry_cr`
  (`manage_land_parcel`) is wired but not seeded by the demo

---

### Scenario 9: Approval workflow on cycles + entitlements

Demonstrate that demo programs route cycles and entitlements through the approval
workflow (a feature MIS demo lacks).

1. Open Input Subsidy → Cycles → click "New Cycle"
2. The cycle enters state `to_approve` (not `draft`) because its cycle manager has
   `approval_definition_id` set
3. Show the approval review record — assigned to `group_programs_manager`, SLA 3 days
4. As Program Manager, approve the cycle → state moves to `approved`
5. Generate entitlements → each entitlement enters `pending_validation` and follows the
   same approval flow

**Key messages:**

- Approval is opt-in per program manager; here every farmer demo program has it wired
- Adding `manager.approval_definition_id` is the only knob — the rest is the standard
  `spp.approval.definition` framework

---

### Scenario 10: GIS + irrigation walk for FM4

Anchor the GIS, land-record, and irrigation modules in a single coherent flow. The
narrative hook: FM4's 1 ha of idle/fallow land is the **downstream consequence of
reduced reservoir capacity**, not random non-cultivation.

1. Open Settings → GIS Configuration → Data Layers and confirm the farmer-registry
   layers are present (Raster + Data Layers reachable, see OP#988 for the menu fix).
2. Open Registry → Groups → FM4 (Mangudadatu Farm). On the GIS view, the farm's land
   parcel polygon is plotted at Cotabato City — ≈ 4 ha total area, of which 1 ha is the
   idle/fallow strip.
3. Open Land Records → filter by `land_farm_id = FM4`. The single record shows the
   parcel polygon and exports as GeoJSON via the action menu
   (`spp.land.record.get_geojson()`).
4. Open Irrigation → Assets → filter by `farm_id = FM4`. Two assets are linked into a
   network:
   - **Cotabato Irrigation Reservoir** (type=reservoir) — effective capacity 5 000 m³;
     design ≈ 15 000 m³ (silted, hence the reduced flow)
   - **Cotabato Main Canal Branch** (type=canal) — fed by the reservoir, 300 m³ flow
     capacity
5. Click the reservoir → see `irrigation_destination_ids` lists the canal. Open the
   canal → `irrigation_source_ids` lists the reservoir. The source-to-destination
   network is the same model used to map nation-scale infrastructure.
6. Back on the map view, apply the spatial layer filter `farm_size_idle > 0` — FM4
   lights up alongside other idle-land farms (mostly the seeded volume blueprints
   `Drought-affected (idle land)` and `Flood-affected female farmer`). This is how a
   ministry planner would target a climate intervention region.
7. Close the loop with Scenario 5 — Climate Resilience already enrolls FM4 because of
   `farm_size_idle > 0`, but **Scenario 10 explains why the idle hectare exists**. The
   two scenarios together make the case that targeting and infrastructure analysis
   belong in the same registry.

**Key messages:**

- The geographic dimension is not just a label — `spp_gis` + `spp_land_record` +
  `spp_irrigation` + `spp_area` compose into a queryable spatial layer
- Compound insight: idle land + degraded irrigation network = a ministry-actionable
  intervention map, not just two unrelated facts
- GeoJSON export is the integration boundary for partners that already operate their own
  GIS stack

---

## References

### Constellation of included registrants

The farmer demo currently supports a single locale (`fil_PH`). Locale-specific name
pools live in `seeded_farm_generator.py`; the per-story names below are the actual
values written by `farmer_demo_generator.py`.

#### Farms used in stories

| Code  | Filipino name                | Story angle                       |
| ----- | ---------------------------- | --------------------------------- |
| FM1   | Santos                       | Smallholder graduation            |
| FM2   | Dela Cruz                    | Multi-program mixed               |
| FM3   | Garcia                       | Senior livestock                  |
| FM4   | Mangudadatu                  | Climate Resilience / idle land    |
| FM5   | Martinez                     | Young female / organic transition |
| FM6   | Dela Cruz (fishpond)         | Aquaculture                       |
| FM7   | Pangandaman                  | Multi-program (Input + Equipment) |
| FM8   | Villanueva                   | Smallholder boundary edge case    |
| EC1   | (volume-generated)           | Large commercial — rejection      |
| EC2   | (volume-generated)           | Idle-only — rejection             |
| EC3   | (volume-generated)           | Inexperienced — partial rejection |
| COOP1 | Nueva Ecija Rice Cooperative | Cooperative (FM1 + FM5)           |
| COOP2 | BARMM Farmers Federation     | Federation (FM4 + FM7)            |

#### Farm information

##### Information about FM1

| Code | Filipino |
| ---- | -------- |
| FM1  | Santos   |

|          | Geographic location          |
| -------- | ---------------------------- |
| Filipino | Cabanatuan City, Nueva Ecija |

| Member ID | Role | Age | Gender | Filipino     |
| --------- | ---- | --- | ------ | ------------ |
| FM1M1     | Head | 42  | Female | Maria Santos |

**Farm facts:** 2.0 ha rice; experience 10 years; productive land 100 %.

##### Information about FM2

| Code | Filipino  |
| ---- | --------- |
| FM2  | Dela Cruz |

|          | Geographic location    |
| -------- | ---------------------- |
| Filipino | San Pablo City, Laguna |

| Member ID | Role | Age | Gender | Filipino       |
| --------- | ---- | --- | ------ | -------------- |
| FM2M1     | Head | 45  | Male   | Juan Dela Cruz |

**Farm facts:** 3.0 ha mixed (1.5 rice + 0.5 vegetables + 50 chickens on 1.0 ha
livestock); experience 15 years.

##### Information about FM3

| Code | Filipino |
| ---- | -------- |
| FM3  | Garcia   |

|          | Geographic location |
| -------- | ------------------- |
| Filipino | Lipa City, Batangas |

| Member ID | Role | Age | Gender | Filipino    |
| --------- | ---- | --- | ------ | ----------- |
| FM3M1     | Head | 67  | Female | Rosa Garcia |

**Farm facts:** 1.0 ha mixed (0.5 ha crops + 0.5 ha livestock with 20 goats); experience
5 years.

##### Information about FM4

| Code | Filipino    |
| ---- | ----------- |
| FM4  | Mangudadatu |

|          | Geographic location                |
| -------- | ---------------------------------- |
| Filipino | Cotabato City, Maguindanao (BARMM) |

| Member ID | Role | Age | Gender | Filipino         |
| --------- | ---- | --- | ------ | ---------------- |
| FM4M1     | Head | 50  | Male   | Amir Mangudadatu |

**Farm facts:** 4.0 ha total (3.0 ha rice + 1.0 ha idle/fallow); experience 20 years;
vulnerability `very_high`.

##### Information about FM5

| Code | Filipino |
| ---- | -------- |
| FM5  | Martinez |

|          | Geographic location              |
| -------- | -------------------------------- |
| Filipino | La Trinidad, Benguet (highlands) |

| Member ID | Role | Age | Gender | Filipino       |
| --------- | ---- | --- | ------ | -------------- |
| FM5M1     | Head | 42  | Female | Sofia Martinez |

**Farm facts:** 2.0 ha vegetables + maize; experience 5 years; organic transition in
progress.

##### Information about FM6

| Code | Filipino  |
| ---- | --------- |
| FM6  | Dela Cruz |

|          | Geographic location |
| -------- | ------------------- |
| Filipino | Dagupan, Pangasinan |

| Member ID | Role | Age | Gender | Filipino        |
| --------- | ---- | --- | ------ | --------------- |
| FM6M1     | Head | 35  | Male   | Ramon dela Cruz |

**Farm facts:** 0.5 ha tilapia fishpond; experience 7 years.

##### Information about FM7

| Code | Filipino    |
| ---- | ----------- |
| FM7  | Pangandaman |

|          | Geographic location           |
| -------- | ----------------------------- |
| Filipino | Marawi, Lanao del Sur (BARMM) |

| Member ID | Role | Age | Gender | Filipino           |
| --------- | ---- | --- | ------ | ------------------ |
| FM7M1     | Head | 32  | Female | Sittie Pangandaman |

**Farm facts:** 1.5 ha rice + vegetables; experience 12 years.

##### Information about FM8

| Code | Filipino   |
| ---- | ---------- |
| FM8  | Villanueva |

|          | Geographic location  |
| -------- | -------------------- |
| Filipino | Malaybalay, Bukidnon |

| Member ID | Role | Age | Gender | Filipino          |
| --------- | ---- | --- | ------ | ----------------- |
| FM8M1     | Head | 38  | Male   | Danilo Villanueva |

**Farm facts:** 5.0 ha mixed (3.0 ha crops + 2.0 ha livestock; 15 cattle + 30 goats);
experience 25 years. Sits exactly at the smallholder boundary.

---

### Configuration of included programs

#### 1. Input Subsidy Program (Group)

| Field             | Value                                                                                                                                     |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Target            | Farm (Group)                                                                                                                              |
| CEL (Eligibility) | `r.is_group == true and is_smallholder and has_productive_land`                                                                           |
| CEL (Compliance)  | `has_productive_land == true and farm_size_hectares > 0`                                                                                  |
| Constants         | `input_subsidy_base` = 100; `per_hectare_subsidy` = 50                                                                                    |
| Entitlement       | base + (farm_size_hectares × per_hectare_subsidy) — e.g. 100 + (2.0 × 50) = ₱200                                                          |
| Cycle             | 30 days                                                                                                                                   |
| Logic Pack        | `farmer_input_subsidy`                                                                                                                    |
| Approval          | Cycle: Program Manager (3-day SLA); Entitlement: Program Manager (3-day SLA)                                                              |
| Compliance Note   | Re-checks productive land each cycle. A farm that abandons productive use becomes `non_compliant` for that cycle and gets no entitlement. |

#### 2. Equipment Grant Program (Group)

| Field             | Value                                                                                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Target            | Farm (Group)                                                                                                                       |
| CEL (Eligibility) | `r.is_group == true and is_smallholder and experience_years >= 2`                                                                  |
| CEL (Compliance)  | `is_smallholder == true and has_productive_land == true`                                                                           |
| Constants         | `equipment_grant_amount` = 500                                                                                                     |
| Entitlement       | ₱500 fixed                                                                                                                         |
| Cycle             | 30 days                                                                                                                            |
| Logic Pack        | `farmer_equipment_grant`                                                                                                           |
| Approval          | Cycle: Program Manager (3-day SLA); Entitlement: Program Manager (3-day SLA)                                                       |
| Compliance Note   | A recipient who grows past the smallholder threshold or stops actively farming fails compliance and stops receiving disbursements. |

#### 3. Livestock Support Program (Group)

| Field       | Value                                                                        |
| ----------- | ---------------------------------------------------------------------------- |
| Target      | Farm (Group)                                                                 |
| CEL         | `r.is_group == true and livestock_count > 0`                                 |
| Constants   | `livestock_base` = 75; `per_head_amount` = 10                                |
| Entitlement | base + (livestock_count × per_head_amount) — e.g. 75 + (20 × 10) = ₱275      |
| Cycle       | 30 days                                                                      |
| Logic Pack  | `farmer_livestock_support`                                                   |
| Approval    | Cycle: Program Manager (3-day SLA); Entitlement: Program Manager (3-day SLA) |

#### 4. Climate Resilience Program (Group)

| Field       | Value                                                                        |
| ----------- | ---------------------------------------------------------------------------- |
| Target      | Farm (Group)                                                                 |
| CEL         | `r.is_group == true and is_smallholder and farm_size_idle > 0`               |
| Constants   | `climate_adaptation_amount` = 200                                            |
| Entitlement | ₱200 fixed                                                                   |
| Cycle       | 30 days                                                                      |
| Logic Pack  | `farmer_climate_resilience`                                                  |
| Approval    | Cycle: Program Manager (3-day SLA); Entitlement: Program Manager (3-day SLA) |

#### 5. Aquaculture Support Program (Group)

| Field       | Value                                                                        |
| ----------- | ---------------------------------------------------------------------------- |
| Target      | Farm (Group)                                                                 |
| CEL         | `r.is_group == true and aquaculture_count > 0`                               |
| Constants   | `aquaculture_amount` = 250                                                   |
| Entitlement | ₱250 fixed                                                                   |
| Cycle       | 30 days                                                                      |
| Logic Pack  | `farmer_aquaculture_support`                                                 |
| Approval    | Cycle: Program Manager (3-day SLA); Entitlement: Program Manager (3-day SLA) |

---

### Overview of included change requests

| #   | Type                 | Target | Registrant | State    | Life event                                               |
| --- | -------------------- | ------ | ---------- | -------- | -------------------------------------------------------- |
| 1   | Update farm details  | Farm   | FM1        | Approved | Farm expanded to 3.0 ha after acquiring adjacent parcel  |
| 2   | Update farm details  | Farm   | FM2        | Applied  | Expanded to 4.0 ha, added livestock area                 |
| 3   | Manage farm activity | Farm   | FM2        | Pending  | Register new chicken-rearing activity (50 heads)         |
| 4   | Update farm details  | Farm   | FM3        | Approved | Land tenure transferred to owner after inheritance       |
| 5   | Manage farm activity | Farm   | FM5        | Draft    | Register organic vegetable cultivation (commercial)      |
| 6   | Manage farm activity | Farm   | FM6        | Pending  | Update tilapia production (3,500 kg current)             |
| 7   | Update farm details  | Farm   | FM4        | Rejected | Reclassify productive area; rejected pending field check |
| 8   | Manage farm activity | Farm   | FM7        | Approved | Register dry-season maize cultivation                    |
| 9   | Update farm details  | Farm   | FM8        | Revision | Experience claim flagged for supporting documents        |
| 10  | Manage farm asset    | Farm   | FM8        | Pending  | Register additional water pump for irrigation expansion  |

**CR types covered:** `update_farm_details`, `manage_farm_activity`,
`manage_farm_asset`. The remaining type shipped by `spp_farmer_registry_cr`
(`manage_land_parcel`) is wired into the module but not seeded by the demo today.

**CR states covered:** Draft, Pending, Approved, Applied (auto-applied on approval for
some CR types), Rejected, Revision.

---

### Geographic distribution

Each story farm is assigned to an administrative area appropriate to its locale from the
demo area data.

| Character                               | Code  | Filipino location            |
| --------------------------------------- | ----- | ---------------------------- |
| Inland rice plains                      | FM1   | Cabanatuan City, Nueva Ecija |
| Inland mixed farming                    | FM2   | San Pablo City, Laguna       |
| Inland plateau, livestock area          | FM3   | Lipa City, Batangas          |
| Inland BARMM, conflict-affected         | FM4   | Cotabato City, Maguindanao   |
| Mountain valley highlands               | FM5   | La Trinidad, Benguet         |
| Inland fishpond area                    | FM6   | Dagupan, Pangasinan          |
| Inland BARMM, women-in-agriculture      | FM7   | Marawi, Lanao del Sur        |
| Inland highland plateau, threshold edge | FM8   | Malaybalay, Bukidnon         |
| Cooperative — Central Luzon             | COOP1 | Nueva Ecija + Benguet        |
| Cooperative — BARMM federation          | COOP2 | Maguindanao + Lanao del Sur  |

---

### Seeded volume blueprints

In addition to the named stories, `seeded_farm_generator.py` produces ~730 volume farms
across 21 deterministic blueprints. Counts and shapes are seed-stable (`seed=42`).

| Blueprint                              | Count | Zone       | Type        | Size (ha) | Experience | Head gender | Members |
| -------------------------------------- | ----- | ---------- | ----------- | --------- | ---------- | ----------- | ------- |
| Small female rice farmer               | 40    | rural      | crop        | 1.0–2.0   | 5–15       | F           | 2       |
| Small male rice farmer                 | 45    | rural      | crop        | 1.0–3.0   | 3–20       | M           | 3       |
| Small maize farmer                     | 35    | rural      | crop        | 1.0–2.5   | 4–18       | M           | 2       |
| Small female vegetable farmer          | 30    | peri-urban | crop        | 0.5–1.5   | 2–12       | F           | 2       |
| Rice + vegetable farmer                | 35    | rural      | crop        | 2.0–4.0   | 8–25       | M           | 4       |
| Highland crop farmer (Cordillera)      | 25    | rural      | crop        | 1.0–2.0   | 5–20       | M           | 3       |
| Mixed rice + chicken                   | 35    | rural      | mixed       | 2.0–3.5   | 5–20       | M           | 3       |
| Mixed maize + goat                     | 30    | rural      | mixed       | 1.5–3.0   | 4–18       | M           | 2       |
| Female-headed mixed rice + cattle      | 30    | rural      | mixed       | 2.0–4.0   | 8–22       | F           | 3       |
| Mixed vegetable + chicken (peri-urban) | 35    | peri-urban | mixed       | 1.0–2.0   | 3–15       | F           | 2       |
| Goat farmer                            | 30    | rural      | livestock   | 1.0–2.5   | 5–20       | M           | 2       |
| Cattle rancher                         | 25    | rural      | livestock   | 3.0–6.0   | 10–30      | M           | 3       |
| Female chicken farmer                  | 35    | peri-urban | livestock   | 0.5–1.5   | 2–12       | F           | 1       |
| Fishpond farmer (tilapia)              | 30    | rural      | aquaculture | 0.5–2.0   | 3–15       | M           | 2       |
| Mixed fishpond + rice                  | 25    | rural      | mixed       | 1.0–3.0   | 5–18       | M           | 3       |
| Large commercial crop                  | 25    | rural      | crop        | 5.0–10.0  | 15–35      | M           | 4       |
| Large mixed commercial                 | 25    | rural      | mixed       | 5.0–8.0   | 12–30      | M           | 3       |
| Drought-affected (idle land)           | 30    | rural      | crop        | 2.0–4.0   | 8–25       | M           | 3       |
| Flood-affected female farmer           | 25    | rural      | crop        | 1.0–2.5   | 5–18       | F           | 2       |
| Young farmer (< 3 years' experience)   | 40    | rural      | crop        | 0.5–2.0   | 0–3        | any         | 1       |
| Elderly farmer (20+ years' experience) | 30    | rural      | crop        | 1.0–3.0   | 20–40      | M           | 2       |

**Total blueprints:** 21. **Total farms:** ~730. **Estimated members:** ~1,500.

---

### Irrigation infrastructure

The demo seeds two `spp.irrigation.asset` records for FM4, linked into a
source-to-destination network. They anchor Scenario 10 (GIS + irrigation walk).

| Asset                         | Type      | Capacity             | farm_id | Source(s)                     | Destination(s)             |
| ----------------------------- | --------- | -------------------- | ------- | ----------------------------- | -------------------------- |
| Cotabato Irrigation Reservoir | Reservoir | 5 000 m³ effective   | FM4     | —                             | Cotabato Main Canal Branch |
| Cotabato Main Canal Branch    | Canal     | 300 m³ flow capacity | FM4     | Cotabato Irrigation Reservoir | —                          |

The reservoir sits a few hundred metres N-W of FM4's parcel; both assets carry GeoJSON
polygons used by the GIS view.

---

### Farm assets

The demo seeds two `spp.farm.asset` machinery records to surface the asset model
alongside the farm-asset CR type.

| Farm | Machinery type | Quantity | Status      | Linked land parcel |
| ---- | -------------- | -------- | ----------- | ------------------ |
| FM1  | Hand Tractor   | 1        | Operational | FM1 main parcel    |
| FM8  | Water Pump     | 1        | Operational | FM8 main parcel    |

A third record is implied by the FM8 `manage_farm_asset` CR (pending) — registering a
second water pump.

---

### Farm seasons

The demo seeds the `spp.farm.season` state machine across both terminal points so
reviewers see all states at a glance.

| Season name                   | Date range                | State  |
| ----------------------------- | ------------------------- | ------ |
| Growing Season {prior year}   | Jan 1 – Dec 31 prior year | Closed |
| Growing Season {current year} | Jan 1 – Dec 31 current    | Active |

The `draft` state is reachable by creating a future season manually in the UI; the demo
doesn't seed one to avoid introducing year-specific assumptions.

---

### Overview

| Metric                   | Count                                                                  |
| ------------------------ | ---------------------------------------------------------------------- |
| Story farms              | 8 (FM1–FM8)                                                            |
| Edge-case stories        | 3 (EC1–EC3)                                                            |
| Cooperative stories      | 2 (COOP1, COOP2)                                                       |
| Total programs included  | 5                                                                      |
| Programs with compliance | 2 (Input Subsidy, Equipment Grant)                                     |
| Change requests          | 10 (3 types, 6 states)                                                 |
| Demo scenarios           | 10                                                                     |
| Irrigation assets        | 2 (reservoir + canal, network linked, anchored on FM4)                 |
| Farm assets              | 2 machinery records seeded (FM1 hand tractor, FM8 water pump)          |
| Farm seasons             | 2 (closed prior year + active current year)                            |
| Locales                  | 1 (`fil_PH`)                                                           |
| Seeded volume            | ~730 farms, ~1,500 individuals                                         |
| Approval definitions     | Cycle + Entitlement (Program Manager, 3-day SLA) on every demo program |
