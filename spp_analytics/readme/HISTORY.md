### 19.0.2.0.1

- feat: expose `spp.analytics.service.get_effective_k_threshold()` so other services that emit their own counts (e.g. GIS spatial queries) can suppress small counts using the caller's access-rule k-anonymity threshold instead of a hardcoded value.

### 19.0.2.0.0

- Initial migration to OpenSPP2
