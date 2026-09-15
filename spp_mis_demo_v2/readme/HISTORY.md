### 19.0.2.1.5

- fix(mis_demo): the Add Newborn demo change request resolves its birthdate against the user's today instead of the server's. `STORY_CHANGE_REQUESTS` is a class attribute, so the `fields.Date.today()` literal it carried was evaluated once at import — and it was the server's UTC date. The birthdate guard added for #362 refuses a date the user has not reached yet, so an admin west of UTC running the generator between 00:00 UTC and their local midnight got a `ValidationError` and demo generation aborted. The definition now declares `birthdate_days_back` and `_build_detail_changes` resolves it with `fields.Date.context_today` at build time.

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
