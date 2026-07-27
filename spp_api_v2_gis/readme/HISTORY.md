### 19.0.2.0.1

- fix(security): apply k-anonymity suppression to registrant counts returned by the spatial-query, batch, and proximity endpoints. A client with `gis:read`/`statistics:read` could previously send tiny polygons or proximity buffers and read `total_count` to learn whether beneficiaries live at a precise location, even when the aggregate statistics were suppressed. Counts below the caller's access-rule k-anonymity threshold (and genuinely empty areas) are now reported as `total_count = 0` with a new `count_suppressed` flag, so small and empty results are indistinguishable.

### 19.0.2.0.0

- Initial migration to OpenSPP2
