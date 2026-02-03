# CEL Event Executor Implementation Notes

## Overview

This document describes the implementation of the CEL executor extension for event data queries in
`/home/user/openspp-modules-v2/spp_cel_event/models/cel_event_executor.py`.

## Architecture

The implementation extends `spp.cel.executor` with support for three event query plan types:

1. **EventValueCompare**: Compare field values from registrant events
2. **EventExists**: Check for event existence
3. **EventsAggregate**: Aggregate values across multiple events

## Key Features

### 1. Dual Execution Paths

Each query plan type has two execution paths:

- **SQL Fast Path**: Optimized SQL for performance at scale
- **Python Fallback**: Full-featured evaluation when SQL not feasible

### 2. SQL Fast Path Implementation

#### EventValueCompare SQL

```sql
SELECT DISTINCT e.partner_id
FROM (
    SELECT DISTINCT ON (e.partner_id) e.*
    FROM spp_event_data e
    WHERE e.event_type_code = 'survey'
      AND e.state IN ('active', 'superseded', 'expired')
      AND e.collection_date >= CURRENT_DATE - INTERVAL '365 days'
    ORDER BY e.partner_id, e.collection_date DESC, e.id DESC
) latest_event
WHERE (latest_event.data_json->>'income')::numeric > 500
```

**Key optimizations:**

- DISTINCT ON for selecting latest/first events
- Indexes on (partner_id, event_type_code, state, collection_date)
- Type casting for JSON field comparisons
- Single query execution for all candidates

#### EventExists SQL

```sql
SELECT DISTINCT e.partner_id
FROM spp_event_data e
WHERE e.event_type_code = 'assessment'
  AND e.state = 'active'
  AND e.collection_date >= CURRENT_DATE - INTERVAL '365 days'
```

**Key optimizations:**

- Simple SELECT DISTINCT for existence check
- Minimal query complexity
- No subqueries needed

#### EventsAggregate SQL

```sql
SELECT e.partner_id
FROM spp_event_data e
WHERE e.event_type_code = 'attendance'
  AND e.state = 'active'
  AND e.collection_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY e.partner_id
HAVING COUNT(*) >= 150
```

**Key optimizations:**

- GROUP BY with HAVING for aggregation
- Direct numeric field extraction from JSON
- Support for count, sum, avg, min, max

### 3. Temporal Filtering

The implementation supports multiple temporal filter types:

| Filter          | SQL Implementation                                       | Notes                                  |
| --------------- | -------------------------------------------------------- | -------------------------------------- |
| `after`         | `collection_date >= %s`                                  | Direct date comparison                 |
| `before`        | `collection_date <= %s`                                  | Direct date comparison                 |
| `within_days`   | `collection_date >= CURRENT_DATE - INTERVAL '%s days'`   | Relative to current date               |
| `within_months` | `collection_date >= CURRENT_DATE - INTERVAL '%s months'` | Relative to current date               |
| `period`        | `collection_date BETWEEN start AND end`                  | Named periods (YYYY, YYYY-QN, YYYY-MM) |

### 4. Selection Modes

| Mode            | SQL Implementation                                          | Default States                        |
| --------------- | ----------------------------------------------------------- | ------------------------------------- |
| `active`        | Simple filter, no ordering                                  | `['active']`                          |
| `latest`        | `DISTINCT ON ... ORDER BY collection_date DESC, id DESC`    | `['active', 'superseded', 'expired']` |
| `latest_active` | `DISTINCT ON ... ORDER BY collection_date DESC, id DESC`    | `['active']`                          |
| `first`         | `DISTINCT ON ... ORDER BY collection_date ASC, id ASC`      | `['active', 'superseded', 'expired']` |
| `any`           | Simple filter, no ordering                                  | `['active']`                          |
| `auto`          | Resolves based on event type `is_one_active_per_registrant` | Varies                                |

### 5. Field Type Handling

JSON field extraction handles multiple data types:

```sql
-- Boolean
(e.data_json->>'field')::boolean = true

-- Numeric (int/float)
(e.data_json->>'field')::numeric > 500

-- String
(e.data_json->>'field') = 'value'

-- NULL
(e.data_json->>'field') IS NULL
```

### 6. Error Handling

- **SQL errors**: Caught and logged, falls back to Python path
- **Type conversion errors**: Handled gracefully with defaults
- **Missing fields**: Returns NULL/None
- **Invalid periods**: Logged warning, returns empty range

## Python Fallback Path

The Python path is used when:

- Default value specified (requires post-processing)
- Complex where predicates in aggregations
- SQL execution fails
- Non-standard comparison operators

**Implementation details:**

- Iterates through candidate registrants
- Builds Odoo domain for event search
- Applies selection mode in Python
- Evaluates comparisons with type coercion

## Performance Characteristics

| Operation                  | Method                          | Complexity | Expected Performance      |
| -------------------------- | ------------------------------- | ---------- | ------------------------- |
| EventValueCompare (SQL)    | Single query with subquery      | O(n log n) | <500ms for 1M registrants |
| EventExists (SQL)          | Simple SELECT DISTINCT          | O(n)       | <200ms for 1M registrants |
| EventsAggregate (SQL)      | GROUP BY with HAVING            | O(n)       | <1s for 1M registrants    |
| EventValueCompare (Python) | Loop with search per registrant | O(n\*m)    | Only for small cohorts    |

## Logging

All execution paths log performance metrics:

```python
_logger.info(
    "[CEL EVENT] EventValueCompare SQL: event_type=%s field=%s op=%s rhs=%s matches=%d",
    plan.event_type,
    plan.field_name,
    plan.op,
    plan.rhs,
    len(partner_ids),
)
```

Log tags:

- `[CEL EVENT]` - Event executor operations
- Includes: event_type, field, operator, RHS value, match count
- Separate log entries for SQL vs Python paths

## Integration Points

### Extends Base Executor

```python
class CelEventExecutor(models.AbstractModel):
    _inherit = "spp.cel.executor"

    def _execute_plan(self, model: str, plan: Any, metrics_info: list[dict[str, Any]] | None = None) -> list[int]:
        if isinstance(plan, EventValueCompare):
            return self._exec_event_value(model, plan)
        # ...
        return super()._execute_plan(model, plan, metrics_info)
```

### Uses Event Data Model

Depends on `spp.event.data` model with:

- Fields: `partner_id`, `event_type_code`, `state`, `collection_date`, `data_json`
- Methods: `get_data_value(field_name, default)`

### Period Parsing

Currently supports:

- `YYYY`: Full year (e.g., '2024')
- `YYYY-QN`: Quarter (e.g., '2024-Q1')
- `YYYY-MM`: Month (e.g., '2024-03')

**TODO**: Add support for:

- `YYYY-HN`: Half year (e.g., '2024-H1')
- `YYYY-WNN`: ISO week (e.g., '2024-W01')

## Testing Recommendations

1. **SQL Path Coverage**

   - Test each selection mode (active, latest, latest_active, first)
   - Test each temporal filter type
   - Test each field type (bool, numeric, string, null)
   - Test each aggregation function (count, sum, avg, min, max)

2. **Python Path Coverage**

   - Test with default values
   - Test error handling
   - Test type coercion

3. **Performance Testing**

   - Benchmark with 100K, 500K, 1M registrants
   - Test with varying event counts per registrant
   - Measure query execution times

4. **Edge Cases**
   - No matching events
   - Missing JSON fields
   - Invalid event type codes
   - Conflicting temporal filters
   - Invalid period formats

## Future Enhancements

1. **SQL where_predicate Support**

   - Parse simple CEL predicates to SQL WHERE clauses
   - Enable SQL fast path for filtered aggregations

2. **Event Type Registry Cache**

   - Cache `is_one_active_per_registrant` flag
   - Avoid repeated lookups in `_resolve_select_mode`

3. **Query Result Caching**

   - Cache results for identical queries within request
   - Invalidate on event data changes

4. **Extended Period Support**

   - Add half-year and ISO week parsing
   - Support dynamic period functions (this_quarter(), last_year())

5. **Batch Optimization**
   - When multiple event conditions in same expression
   - Combine into single query with JOINs

## Dependencies

- `odoo.models`: Base model framework
- `odoo.tools.sql.SQL`: SQL query builder
- `spp_cel_domain`: Base CEL executor
- `spp_event_data`: Event data model

## Files Modified

1. `/home/user/openspp-modules-v2/spp_cel_event/models/cel_event_executor.py` (created)
2. `/home/user/openspp-modules-v2/spp_cel_event/models/__init__.py` (updated import)
