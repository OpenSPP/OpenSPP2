Unified aggregation service that all consumers (simulation API, GIS API, dashboards)
use to compute population statistics with demographic breakdowns and privacy
enforcement. Resolves a scope (CEL expression, area, polygon, explicit IDs) to
registrant IDs, computes requested statistics, applies k-anonymity suppression,
and caches results.

### Key Capabilities

- Single entry point (`spp.aggregation.service.compute_aggregation`) for all analytics queries
- Scope resolution: CEL expressions, admin areas, area tags, spatial polygons/buffers, explicit IDs
- Multi-dimensional breakdown (up to 3 dimensions) using demographic dimensions
- Result caching with configurable TTL and manual invalidation
- Per-user access rules controlling scope types, dimensions, and k-anonymity thresholds

### Key Models

| Model                          | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| `spp.aggregation.scope`        | Defines what to aggregate (CEL, area, polygon, explicit IDs)|
| `spp.aggregation.access.rule`  | Per-user/group access level, scope restrictions, k-threshold|
| `spp.aggregation.cache.entry`  | Cached aggregation results                                  |
| `spp.aggregation.service`      | Abstract service: main aggregation entry point              |
| `spp.aggregation.scope.resolver` | Abstract service: resolves scopes to registrant IDs       |
| `spp.aggregation.statistic.registry` | Abstract service: dispatches statistic computation   |

### Configuration

After installing:

1. Navigate to **Settings > Aggregation > Configuration > Scopes** to define reusable scopes
2. Configure **Access Rules** to set per-user/group privacy levels and scope restrictions
3. Verify the **Cache Cleanup** scheduled action is active under **Settings > Technical > Scheduled Actions**

### UI Location

- **Menu**: Settings > Aggregation > Configuration > Scopes
- **Menu**: Settings > Aggregation > Configuration > Demographic Dimensions
- **Menu**: Settings > Aggregation > Configuration > Access Rules

### Security

| Group                         | Access                           |
| ----------------------------- | -------------------------------- |
| `group_aggregation_read`      | Read scopes and cache entries    |
| `group_aggregation_write`     | Full CRUD on scopes and cache    |
| `group_aggregation_manager`   | Full CRUD on access rules        |

### Extension Points

- Add new scope types by extending `spp.aggregation.scope` and `spp.aggregation.scope.resolver`
- Register custom statistics via `spp.aggregation.statistic.registry`
- Override `_compute_single_statistic()` for custom computation logic

### Dependencies

`base`, `spp_cel_domain`, `spp_area`, `spp_registry`, `spp_security`, `spp_metrics_services`
