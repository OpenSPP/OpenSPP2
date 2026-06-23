Adds source/provenance tracking to program memberships (`spp.program.membership`). Split out of `spp_source_tracking` so the base source-tracking module no longer depends on `spp_programs` — registry-only deployments get source tracking without the Programs stack.

Auto-installs whenever both `spp_source_tracking` and `spp_programs` are present, so program-membership source tracking is unchanged where programs are used.

### Dependencies

`spp_source_tracking`, `spp_programs`
