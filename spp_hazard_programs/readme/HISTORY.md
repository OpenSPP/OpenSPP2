### 19.0.2.0.1

- fix(security): read `spp.hazard.impact` via `sudo` in the emergency-eligibility computes (`affected_registrant_count`, `get_emergency_eligible_registrants`), so they keep working for non-hazard program users after impact read access was restricted to hazard/registry roles. Only aggregate counts are surfaced to program users without impact read; the list of eligible (impacted) registrants is the identity linkage the impact ACL protects, so `action_view_affected_registrants` now checks impact read access server-side, its stat button is gated in the form, and `get_emergency_eligible_registrants()` is renamed `_get_emergency_eligible_registrants()` so it is no longer callable over RPC (Python callers and overrides are unaffected).

### 19.0.2.0.0

- Initial migration to OpenSPP2
