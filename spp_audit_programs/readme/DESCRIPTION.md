Ships the audit rules for program and cycle models. Split out of `spp_audit` so the base audit module no longer depends on `spp_programs` — modules that only need registry/service-point auditing (and everything that depends on `spp_audit`, e.g. `spp_studio`) no longer pull in the Programs stack.

Auto-installs whenever both `spp_audit` and `spp_programs` are present, so program auditing is unchanged where programs are used.

### Dependencies

`spp_audit`, `spp_programs`
