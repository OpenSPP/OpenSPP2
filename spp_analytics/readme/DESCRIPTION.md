Unified analytics service that all consumers (simulation API, GIS API, dashboards)
use to compute population statistics with demographic breakdowns and privacy
enforcement. Resolves a scope (CEL expression, area, polygon, explicit IDs) to
registrant IDs, computes requested statistics, applies k-anonymity suppression,
and caches results.

### Key Capabilities

- Single entry point (`spp.analytics.service.compute_aggregation`) for all analytics queries
- Scope resolution: CEL expressions, admin areas, area tags, spatial polygons/buffers, explicit IDs
- Indicator registry with built-in statistics (count, gini) and extensible via CEL variables
- Multi-dimensional breakdown (up to 3 dimensions) using demographic dimensions
- Result caching with per-scope-type TTL and manual invalidation
- Per-user access rules controlling scope types, dimensions, and k-anonymity thresholds

### Key Models

| Model                                | Description                                                  |
| ------------------------------------ | ------------------------------------------------------------ |
| `spp.analytics.scope`               | Defines what to aggregate (CEL, area, polygon, explicit IDs) |
| `spp.analytics.access.rule`         | Per-user/group access level, scope restrictions, k-threshold |
| `spp.analytics.cache.entry`         | Cached aggregation results with TTL expiration               |
| `spp.analytics.service`             | Abstract service: main aggregation entry point               |
| `spp.analytics.scope.resolver`      | Abstract service: resolves scopes to registrant IDs          |
| `spp.analytics.indicator.registry`  | Abstract service: maps statistic names to computation logic  |
| `spp.analytics.cache`               | Abstract service: cache operations with TTL management       |

### Configuration

After installing:

1. Navigate to **Settings > Analytics > Configuration > Scopes** to define reusable scopes
2. Configure **Access Rules** to set per-user/group privacy levels and scope restrictions
3. Verify the **Cache Cleanup** scheduled action is active under **Settings > Technical > Scheduled Actions**

### UI Location

- **Menu**: Settings > Analytics > Configuration > Scopes
- **Menu**: Settings > Analytics > Configuration > Demographic Dimensions
- **Menu**: Settings > Analytics > Configuration > Access Rules

### Security

| Group                            | Access                                            |
| -------------------------------- | ------------------------------------------------- |
| `group_aggregation_read`         | Read scopes and cache entries (Tier 3 technical)  |
| `group_aggregation_write`        | Write scopes and cache entries (Tier 3 technical) |
| `group_aggregation_viewer`       | View aggregate statistics only (Tier 2)           |
| `group_aggregation_officer`      | Query with individual record access (Tier 2)      |
| `group_aggregation_manager`      | Full management including access rules (Tier 2)   |

### Extension Points

- Add new scope types by extending `spp.analytics.scope` and `spp.analytics.scope.resolver`
- Register custom statistics via `spp.analytics.indicator.registry`
- Override `_compute_single_statistic()` for custom computation logic

### Dependencies

`base`, `spp_cel_domain`, `spp_area`, `spp_registry`, `spp_security`, `spp_metric_service`
