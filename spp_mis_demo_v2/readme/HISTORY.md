### 19.0.2.2.0

- fix(demo): **enrollment now follows each program's eligibility rule.** Households were enrolled from a static per-blueprint flag while the program form previewed its CEL, so a program could claim 102 enrolled households while matching 9. Programs with a selective rule enrol whoever that rule matches; Food Assistance and Emergency Relief Fund stay flag-driven, the first because its expression matches every active registrant and the second because it has none (#956)
- fix(demo): a reconciliation pass enrols registrants a program matches but nothing enrolled. The volume pass evaluates each rule against the households it generates and the story pass works from scripts, so a story household satisfying a program's rule without being scripted into it stayed out: the Cash Transfer Program matched 22 and enrolled 14. It runs after both, so scripted enrollments and the dates, payments and entitlements they carry are never pre-empted. Measured on a real Load Demo, every program with a targeting rule now matches its membership count exactly (#956)
- fix(demo): **generated ages are no longer a year out.** A member asked for at age N was created at N+1 whenever their random birth month fell before the reference month, which is eight times in twelve, so programs with age predicates matched a fraction of the households meant for them (#956)
- fix(demo): **members flagged as disabled are recorded as such.** Blueprints mark specific members `is_disabled`, and nothing acted on it, so no registrant had a disability and the Disability Support Grant matched nothing. Each flagged member now gets an approved assessment carrying answers that meet the Washington Group threshold. Adds a dependency on `spp_disability_registry`, without which `res.partner.has_disability` does not exist at all (#955)
- fix(demo): the `disabled_count` aggregate filtered on `is_person_with_disability`, a field that exists nowhere, so it counted zero on every household (#955)
- fix(demo): **cycle and entitlement managers get their approval workflow.** Neither carried an approval definition, which is not a soft gap: approving a cycle raised "The cycle approval definition is not specified!" and preparing entitlements raised its equivalent, so the demo could not show either flow. Wired as its own pass, since neither manager-configuration step reached every program (#957)
- fix(demo): a compliance manager is only created for a program that has a compliance rule. An empty one is not harmless -- `has_compliance_criteria` and the cycle's compliance filter are both derived from its mere existence, so the UI offered filtering that could never match (#1017)
- fix(demo): manager repair is per record rather than per list. A wrapper whose concrete manager had been deleted was never rebuilt, because a non-empty list was skipped wholesale; the program card kept offering a method with nothing behind it (#1017)
- fix(demo): manager wrappers belonging to archived or deleted programs are swept at the start of each run instead of accumulating (#1017)

### 19.0.2.1.4

- revert(mis_demo): the Add Member and Change Head of Household demo CRs match the reinstated old flows (see `spp_change_request_v2` #871/#873 revert) — Add Member builds a new individual (given/family name, birthdate, relationship) and Change HoH sets `new_head_id` from the named new head, instead of the redesigned `individual_id` / per-member role lines.

### 19.0.2.1.3

- fix: PHL story registrants map to the curated PSGC p-code area external IDs introduced by the re-landed spp_demo geodata (`STORY_AREA_MAP` still referenced the removed named IDs, silently dropping area assignments).

### 19.0.2.1.2

- fix: demo GIS reports use `dimension_ids` + `member_expansion` instead of the removed `disaggregate_by_*` boolean fields (ported from #295, credit @kneckinator; required in lockstep with the spp_gis_report dimension change).

### 19.0.2.1.1

- feat(demo): adapt the change-request demo generator to the redesigned CR flows — Add Member selects an existing individual (#871) and Change Head of Household uses per-member role lines (#873) (#242)

### 19.0.2.1.0

- feat(demo): seed country-appropriate CR document types (≥5 per country for PHL / LKA / TGO) into the `cr_document_type` vocabulary during demo generation, so a document type can be selected when attaching files to a change request without defining them manually (#1102)

### 19.0.2.0.0

- Initial migration to OpenSPP2
