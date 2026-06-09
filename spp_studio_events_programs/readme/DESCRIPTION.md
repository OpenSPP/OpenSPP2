Re-adds program scoping to Studio event types. Split out of `spp_studio_events` so the base module no longer depends (transitively) on `spp_programs` — deployments without programs can use Studio events without installing the Programs stack.

Auto-installs whenever both `spp_studio_events` and `spp_studio_programs` are present, so the program-scoping page reappears on the event type form exactly where programs are used.

### Key Capabilities

- Injects the Programs page (`program_ids`) back into the event type form

### Dependencies

`spp_studio_events`, `spp_studio_programs`
