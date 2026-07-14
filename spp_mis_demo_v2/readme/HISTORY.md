### 19.0.2.1.2

- fix: demo GIS reports use `dimension_ids` + `member_expansion` instead of the removed `disaggregate_by_*` boolean fields (ported from #295, credit @kneckinator; required in lockstep with the spp_gis_report dimension change).

### 19.0.2.1.1

- feat(demo): adapt the change-request demo generator to the redesigned CR flows — Add Member selects an existing individual (#871) and Change Head of Household uses per-member role lines (#873) (#242)

### 19.0.2.1.0

- feat(demo): seed country-appropriate CR document types (≥5 per country for PHL / LKA / TGO) into the `cr_document_type` vocabulary during demo generation, so a document type can be selected when attaching files to a change request without defining them manually (#1102)

### 19.0.2.0.0

- Initial migration to OpenSPP2
