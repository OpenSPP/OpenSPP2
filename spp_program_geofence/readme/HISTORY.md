## 19.0.1.0.1

- fix(security): route the async import lock through the operation-lock
  helpers so it keeps working under the new `spp.program` write guard.
  `spp_programs` 19.0.2.2.2 restricts direct writes to `is_locked` /
  `locked_reason` to system administrators; the geofence import acquired and
  released the lock with plain writes as the initiating (non-admin) user,
  which the guard would reject — leaving the program stuck locked. It now
  uses `_acquire_operation_lock` / `_release_operation_lock` (which `sudo()`).

## 19.0.1.0.0

- Initial release: geofence-based program targeting and eligibility management (Tier 1 coordinate intersection, Tier 2 area-intersection fallback), program configuration UI, and program creation wizard support.
