Unified aggregation engine for computing statistics, breakdowns, and fairness metrics over scoped registrant populations. Supports multiple scope types (CEL expressions, areas, spatial queries, explicit IDs) with access control, caching, and privacy enforcement.

### Key Capabilities

- Define reusable aggregation scopes: CEL expression, area, area tag, spatial polygon/buffer, or explicit registrant IDs
- Resolve scopes to registrant sets with union and intersection operations
- Compute statistics (count, Gini) with extensible statistic registry supporting CEL variables
- Role-based access control with per-user scope type restrictions, dimension limits, and area constraints
- Result caching with configurable TTL per scope type and automatic cleanup
- Privacy enforcement via k-anonymity suppression on computed results
- Convenience methods for area-based, expression-based, fairness, and distribution queries

### Key Models

| Model                              | Type     | Description                                       |
| ---------------------------------- | -------- | ------------------------------------------------- |
| `spp.aggregation.scope`            | Concrete | Configurable aggregation scope definitions        |
| `spp.aggregation.access.rule`      | Concrete | Per-user/group access control rules               |
| `spp.aggregation.cache.entry`      | Concrete | Persistent cache entries with TTL                 |
| `spp.aggregation.scope.resolver`   | Abstract | Strategy-based scope resolution service           |
| `spp.aggregation.cache`            | Abstract | Cache service with TTL and cleanup                |
| `spp.aggregation.statistic.registry` | Abstract | Statistic computation registry (builtins + CEL) |
| `spp.aggregation.service`          | Abstract | Main aggregation entry point                      |

### Configuration

- Aggregation scopes: **Settings > Aggregation > Aggregation Scopes**
- Access rules: **Settings > Aggregation > Access Rules**
- Cache cleanup runs daily via scheduled action

### Security

| Group                                   | Access                                    |
| --------------------------------------- | ----------------------------------------- |
| `spp_aggregation.group_aggregation_read`    | Read-only access to scopes and cache  |
| `spp_aggregation.group_aggregation_write`   | Read/write scopes and access rules    |
| `spp_aggregation.group_aggregation_viewer`  | Implied by write group                |
| `spp_aggregation.group_aggregation_officer` | Implied by viewer group               |
| `spp_aggregation.group_aggregation_manager` | Full access, implied by admin         |

### Dependencies

`base`, `spp_cel_domain`, `spp_area`, `spp_registry`, `spp_security`, `spp_metrics_services`
