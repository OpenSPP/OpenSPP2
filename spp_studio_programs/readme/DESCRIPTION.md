Adds program scoping to OpenSPP Studio (no-code) configurations. Split out of `spp_studio` so the base Studio module no longer depends on `spp_programs` — deployments without programs can use Studio without installing the Programs stack.

Auto-installs whenever both `spp_studio` and `spp_programs` are present, so program-scoping behaviour is unchanged where programs are used.

### Key Capabilities

- Adds the optional `program_ids` link on Studio configurations (`spp.studio.mixin`), so fields / logic variables can be scoped to specific programs
- Adds the optional `program_id` on the Logic Pack install wizard for program-specific constant-value lookups

### Dependencies

`spp_studio`, `spp_programs`
