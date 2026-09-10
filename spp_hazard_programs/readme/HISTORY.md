### 19.0.2.0.1

- fix(security): read `spp.hazard.impact` via `sudo` in the emergency-eligibility computes (`affected_registrant_count`, `get_emergency_eligible_registrants`), so they keep working for non-hazard program users after impact read access was restricted to hazard/registry roles. Only aggregate counts / eligible registrants are surfaced, not impact rows.

### 19.0.2.0.0

- Initial migration to OpenSPP2
