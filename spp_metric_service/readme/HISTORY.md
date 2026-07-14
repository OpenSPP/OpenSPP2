### 19.0.2.1.0

- feat: demographic breakdown expansion and SQL column support for metric disaggregation (re-land from #76; uses the spp_cel_domain SQL CASE compiler). Expansion is all-or-nothing: any individuals-scoped dimension expands the whole registrant set to active members, so breakdown totals count members and need not reconcile with a group-level scope count.

### 19.0.2.0.0

- Initial migration to OpenSPP2
