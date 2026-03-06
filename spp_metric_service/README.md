# OpenSPP Metric Service

Computation services for metrics across OpenSPP modules.

## Overview

`spp_metric_service` provides the core computation engine for all metrics in OpenSPP,
including population statistics, simulation outcomes, fairness analysis, and privacy
protection. These services are used by GIS, dashboards, simulations, and APIs.

## Architecture

```
spp.analytics.service (Main Entry Point)
    │
    ├── spp.metric.breakdown (Multi-dimensional grouping)
    │   └── spp.metric.dimension.cache (Performance optimization)
    ├── spp.metric.fairness (Equity analysis)
    ├── spp.metric.distribution (Statistical distributions)
    └── spp.metric.privacy (K-anonymity enforcement)
```

## Services

### spp.analytics.service

**Main entry point** for all aggregation computations.

**Key Method:**

```python
compute_aggregation(scope, statistics=None, group_by=None, context=None)
```

**Arguments:**

- `scope` - Dict defining the population (scope_type + params)
- `statistics` - List of metric names to compute (or None for defaults)
- `group_by` - List of dimension names for breakdown (max 3)
- `context` - Context string ('gis', 'api', 'dashboard', etc.)

**Returns:**

```python
{
    'total_count': 123,
    'statistics': {
        'total_registrants': {'value': 123, 'suppressed': False},
        'coverage_rate': {'value': 45.2, 'suppressed': False},
    },
    'breakdown': {
        'dimensions': ['gender', 'age_group'],
        'groups': [
            {
                'dimension_values': {'gender': 'M', 'age_group': '18-24'},
                'count': 15,
                'statistics': {...},
            },
            ...
        ],
    },
}
```

**Example:**

```python
service = env['spp.analytics.service']

scope = {
    'scope_type': 'area',
    'area_id': 42,
}

result = service.compute_aggregation(
    scope=scope,
    statistics=['total_registrants', 'coverage_rate'],
    group_by=['gender', 'disability'],
    context='gis',
)
```

### spp.metric.breakdown

Computes multi-dimensional breakdowns with caching.

**Key Method:**

```python
compute_breakdown(registrant_ids, group_by, statistics=None, context=None)
```

**Features:**

- Supports up to 3 simultaneous dimensions
- Automatic caching via `spp.metric.dimension.cache`
- Privacy enforcement on small groups

**Example:**

```python
breakdown_service = env['spp.metric.breakdown']

result = breakdown_service.compute_breakdown(
    registrant_ids=[1, 2, 3, 4, 5],
    group_by=['gender', 'age_group'],
    statistics=['total_registrants'],
    context='gis',
)
```

### spp.metric.fairness

Computes fairness/equity metrics across demographic groups.

**Key Method:**

```python
compute_fairness(registrant_ids, base_domain=None, dimensions=None)
```

**Returns:**

- Equity score (0-100, higher is more equitable)
- Disparity detection (boolean)
- Per-dimension analysis with max ratio

**Metrics Computed:**

- Representation ratio (actual / expected)
- Max disparity across all groups
- Coverage by dimension

**Example:**

```python
fairness_service = env['spp.metric.fairness']

result = fairness_service.compute_fairness(
    registrant_ids=[1, 2, 3],
    base_domain=[('active', '=', True)],
    dimensions=['gender', 'disability'],
)

# Result:
# {
#     'equity_score': 85.5,
#     'has_disparity': True,
#     'by_dimension': {
#         'gender': {
#             'max_ratio': 1.8,
#             'groups': {...},
#         },
#     },
# }
```

### spp.metric.distribution

Computes distribution statistics for numerical values.

**Key Method:**

```python
compute_distribution(amounts)
```

**Returns:**

- Descriptive statistics (mean, median, min, max, std dev, variance)
- Percentiles (p10, p25, p50, p75, p90)
- Gini coefficient (inequality measure)
- Lorenz curve deciles (inequality visualization)

**Example:**

```python
distribution_service = env['spp.metric.distribution']

amounts = [100, 200, 150, 300, 250]
stats = distribution_service.compute_distribution(amounts)

# Result:
# {
#     'mean': 200.0,
#     'median': 200.0,
#     'gini': 0.18,
#     'percentiles': {'p50': 200.0, ...},
#     'lorenz_curve': [0.0, 0.15, 0.32, ...],
# }
```

### spp.metric.privacy

Enforces k-anonymity privacy protection on aggregation results.

**Key Methods:**

```python
enforce(result, k_threshold=None, access_level="aggregate")
suppress_value(value, count, k_threshold=None, stat_config=None)
```

**Features:**

- K-anonymity with complementary suppression
- Access level enforcement (aggregate vs individual)
- Protection against differencing attacks
- Configurable thresholds per context

**Example:**

```python
privacy_service = env['spp.metric.privacy']

result = {
    'total_count': 3,  # Below threshold
    'statistics': {'total_registrants': {'value': 3}},
}

protected = privacy_service.enforce(result, k_threshold=10)

# Result:
# {
#     'total_count': 0,  # Suppressed
#     'statistics': {'total_registrants': {'value': 0, 'suppressed': True}},
#     'suppressed': True,
#     'suppression_reason': 'Group size below k-anonymity threshold',
# }
```

### spp.metric.dimension.cache

Performance cache for dimension evaluations.

**Key Methods:**

```python
get_cached_dimension(dimension_id, registrant_ids)
cache_dimension_results(dimension_id, results)
invalidate_dimension(dimension_id)
```

**Features:**

- 5-10x faster repeated evaluations
- Automatic invalidation on dimension changes
- Cache key: (dimension_id, write_date, registrant_ids hash)
- Automatic cleanup of stale entries

**Cache Strategy:**

```python
# First call: Evaluates CEL expression
result = breakdown.compute_breakdown(dimension_ids, registrant_ids)

# Subsequent calls: Uses cached results
result = breakdown.compute_breakdown(dimension_ids, registrant_ids)  # Fast!

# After dimension.write(): Cache invalidated automatically
dimension.write({'cel_expression': 'new_expr'})
result = breakdown.compute_breakdown(dimension_ids, registrant_ids)  # Re-evaluates
```

## Dependencies

- `base` - Odoo core
- `spp_metric` - Base metric models
- `spp_cel_domain` - CEL expression support
- `spp_area` - Administrative areas
- `spp_registry` - Registrant/partner data

## Used By

- `spp_analytics` - Delegates to these services
- `spp_indicator` - Indicator computation
- `spp_simulation` - Simulation metrics
- `spp_api_v2_gis` - GIS statistics API
- `spp_api_v2_simulation` - Simulation API

## Migration from spp_analytics

These services were extracted from `spp_analytics` to enable reuse across modules.

**No code changes required** - Existing code continues to work:

```python
# Still works
fairness = env['spp.metric.fairness']
distribution = env['spp.metric.distribution']
privacy = env['spp.metric.privacy']
breakdown = env['spp.metric.breakdown']
```

See [Migration Guide](../../docs/migration/statistics-refactoring.md) for details.

## Performance Considerations

### Caching

Dimension cache eliminates redundant CEL evaluations:

- **First call**: Evaluates CEL expression (~500ms for 10k registrants)
- **Cached calls**: Retrieves cached results (~50ms)
- **Invalidation**: Automatic on dimension.write()

### Batch Processing

For large populations (>10,000 registrants):

```python
# Use explicit scope to avoid repeated CEL evaluation
scope = {
    'scope_type': 'explicit',
    'explicit_partner_ids': large_list_of_ids,
}

result = service.compute_aggregation(scope=scope, ...)
```

### Privacy Overhead

K-anonymity enforcement adds minimal overhead:

- Group size check: O(1)
- Suppression logic: O(n) where n = number of groups
- Typical overhead: <1% of total computation time

## Testing

Run tests:

```bash
./scripts/test_single_module.sh spp_metric_service
```

Key test scenarios:

- Service computation accuracy
- Cache hit/miss rates
- Privacy enforcement
- Multi-dimensional breakdowns
- Large population handling

## Architecture Documentation

See [Statistics System Architecture](../../docs/architecture/statistics-systems.md) for
the complete system design.

## License

LGPL-3
