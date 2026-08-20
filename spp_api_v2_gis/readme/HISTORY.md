### 19.0.2.0.2

- fix(security): apply k-anonymity suppression to registrant counts returned by the spatial-query, batch, and proximity endpoints. A client with `gis:read`/`statistics:read` could previously send tiny polygons or proximity buffers and read `total_count` — or the presence of accompanying `statistics`/`access_level`/`computed_at`/`query_method` metadata — to learn whether beneficiaries live at a precise location, even when the aggregate statistics were suppressed. When the count is below the caller's access-rule k-anonymity threshold (which includes genuinely empty areas), the response is now canonicalized: `total_count = 0`, a new `count_suppressed` flag is set, and every people-correlated field (`statistics`, `access_level`, `from_cache`, `computed_at`, `query_method`, `areas_matched`) is blanked to a fixed value, so a small region and an empty one are byte-identical and no field can be used as a presence oracle.

### 19.0.2.0.0

- Initial migration to OpenSPP2
