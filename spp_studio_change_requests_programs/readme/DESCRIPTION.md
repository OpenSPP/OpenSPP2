Re-adds program scoping to Studio change request types. Split out of `spp_studio_change_requests` so the base module no longer depends (transitively) on `spp_programs` — deployments without programs can use Studio change requests without installing the Programs stack.

Auto-installs whenever both `spp_studio_change_requests` and `spp_studio_programs` are present, so the program-scoping field reappears on the change request type form exactly where programs are used.

### Key Capabilities

- Injects the `program_ids` field back into the change request type form (Technical Info → Programs)

### Dependencies

`spp_studio_change_requests`, `spp_studio_programs`
