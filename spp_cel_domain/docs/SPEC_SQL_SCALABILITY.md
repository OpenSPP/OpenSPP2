# CEL Domain SQL Scalability Specification

**Version**: 2.0 **Status**: Final Draft **Date**: 2024-12

---

## 1. Executive Summary

This specification defines improvements to the CEL (Common Expression Language) domain
evaluation system to support scaling from 100K to 10M+ beneficiaries.

**Core Principle**: Generate SQL subqueries that execute entirely in PostgreSQL,
avoiding Python memory materialization of large ID lists.

**Key Decisions**:

- **Single execution mode**: SQL-first with Python fallback (no hybrid mode)
- **Record rules**: Inject via Odoo's `expression.expression()` for all subqueries
- **MetricCompare**: Already has SQL path when cache is fresh; no changes needed

---

## 2. Problem Statement

### 2.1 Current Issues

| Issue                | Severity | Root Cause                                                        |
| -------------------- | -------- | ----------------------------------------------------------------- |
| Memory exhaustion    | CRITICAL | `search().ids` loads ALL matching IDs into Python                 |
| Operator support gap | CRITICAL | Only `=` works in default_domain; `!=`, `>`, `<` silently dropped |
| AND short-circuit    | HIGH     | One non-SQL child fails entire AND expression                     |
| No aggregation SQL   | HIGH     | `members.sum()`, `members.avg()` always use Python                |

### 2.2 Target Scale

| Deployment | Records | Preview Response | Batch Processing |
| ---------- | ------- | ---------------- | ---------------- |
| Small      | 100K    | < 500ms          | < 1 min          |
| Medium     | 1M      | < 2s             | < 10 min         |
| Large      | 10M+    | < 5s             | < 1 hour         |

### 2.3 Success Criteria

1. Memory usage bounded regardless of result set size (max ~50MB for preview)
2. All comparison operators work correctly
3. SQL path covers >90% of common expressions
4. Results identical between SQL and Python paths
5. Record rules respected in all SQL subqueries
6. Clear feedback when expression cannot use SQL path

---

## 3. Architecture

### 3.1 Design Principles

1. **SQL-first**: Always attempt SQL generation; fall back to Python only when
   impossible
2. **No hybrid mode**: Either entire expression is SQL, or entire expression is Python
3. **Record rules via ORM**: Use `expression.expression()` for all subqueries to ensure
   security
4. **Bounded memory**: Never load all IDs; use `search_count()` + `search(limit=N)`
5. **Clear feedback**: Return execution path and warnings in response

### 3.2 Execution Flow

```
compile_expression(expr):

    plan = parse_and_translate(expr)

    # Step 1: Try SQL path
    sql = plan_to_sql(plan)

    if sql is not None:
        # SQL path - scales to millions
        domain = base_domain + [("id", "in", sql)]
        count = search_count(domain)           # Efficient count
        preview_ids = search(domain, limit=N)  # Only load preview
        return {
            count: count,
            preview_ids: preview_ids,
            path: "sql",
            warnings: []
        }

    # Step 2: Python fallback with warning
    warning = "Expression requires Python path: {reason}. May be slow at scale."
    ids = execute_plan_python(plan)
    return {
        count: len(ids),
        preview_ids: ids[:N],
        path: "python",
        warnings: [warning]
    }
```

### 3.3 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CEL Service                                 │
│                  compile_expression()                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CEL Executor                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    SQL Builder                              │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │ │
│  │  │  term()  │ │ where()  │ │ select() │ │  aggregate()  │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            │                                     │
│              ┌─────────────┴─────────────┐                      │
│              ▼                           ▼                      │
│     ┌─────────────────┐         ┌─────────────────┐             │
│     │  plan_to_sql()  │         │ execute_python()│             │
│     │   (preferred)   │         │   (fallback)    │             │
│     └─────────────────┘         └─────────────────┘             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Odoo ORM                                   │
│              search_count() / search(limit=N)                    │
│         (applies record rules, multi-company, active)            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Record Rules Strategy

**Problem**: SQL JOINs can bypass Odoo record rules on joined tables.

**Solution**: Always use `expression.expression()` to generate subqueries, which
automatically includes record rules.

```
# WRONG - bypasses record rules on res_partner:
SELECT m.group FROM membership m
JOIN res_partner p ON p.id = m.individual
WHERE p.income > 5000

# CORRECT - record rules applied via expression.expression():
SELECT m.group FROM membership m
WHERE m.individual IN (
    SELECT id FROM res_partner WHERE income > 5000
    -- expression.expression() adds: AND company_id IN (...) AND active = true
)
```

**Implementation Rule**: Every reference to a model MUST go through
`_domain_to_id_sql()` which uses `expression.expression()`.

---

## 4. SQL Builder Module

### 4.1 Module Structure

```
spp_cel_domain/
├── models/
│   ├── cel_executor.py      # Main executor (modified)
│   ├── cel_sql_builder.py   # NEW - SQL generation utilities
│   └── ...
```

### 4.2 SQL Builder Interface

```
class SQLBuilder:
    """Composable SQL query builder using Odoo's SQL class.

    All methods return SQL objects or None if conversion not possible.
    All subqueries use expression.expression() to include record rules.
    """

    # === Term Builder ===

    term(alias, field, op, value) -> SQL | None
        """Convert a single comparison to SQL.

        Supported operators: =, !=, >, >=, <, <=, in, not in
        NULL handling: = None becomes IS NULL, != None becomes IS NOT NULL

        Returns None for unsupported operators (like, ilike, child_of).

        Examples:
            term("m", "is_ended", "=", False)    -> SQL("m.is_ended = %s", False)
            term("m", "status", "!=", "ended")   -> SQL("m.status != %s", "ended")
            term("m", "count", ">=", 5)          -> SQL("m.count >= %s", 5)
            term("m", "field", "=", None)        -> SQL("m.field IS NULL")
            term("m", "ids", "in", [1,2,3])      -> SQL("m.ids IN %s", (1,2,3))
            term("m", "name", "like", "%x%")     -> None (unsupported)
        """

    # === WHERE Clause Builder ===

    where_and(conditions: list[SQL]) -> SQL
        """Combine conditions with AND.

        Empty list returns SQL("1=1").
        Single condition returns that condition.
        Multiple conditions combined with AND.
        """

    # === SELECT Builders ===

    select_ids_from_domain(model, domain) -> SQL | None
        """Generate SELECT id FROM model WHERE domain.

        Uses expression.expression() to include record rules.
        Returns None if domain cannot be converted.

        This is the PRIMARY method for generating subqueries.
        All other methods should use this for model references.
        """

    select_distinct_column(table, alias, column, where) -> SQL
        """SELECT DISTINCT column FROM table WHERE ...

        Used for ExistsThrough to get parent IDs.
        """

    select_grouped_count(table, alias, group_col, where, having_op, having_value) -> SQL
        """SELECT with GROUP BY and HAVING COUNT(*).

        Used for CountThrough.

        Example:
            select_grouped_count(
                "spp_group_membership", "m", "group",
                where=SQL("m.is_ended = false"),
                having_op=">=", having_value=2
            )
            -> SELECT m.group FROM spp_group_membership m
               WHERE m.is_ended = false
               GROUP BY m.group
               HAVING COUNT(*) >= 2
        """

    select_grouped_aggregate(
        through_table, through_alias,
        child_subquery,           # FROM select_ids_from_domain()
        parent_col, link_col,
        agg_func, agg_field,
        having_op, having_value
    ) -> SQL
        """SELECT with aggregate function on joined data.

        Used for FieldAggregateThrough (sum, avg, min, max).

        IMPORTANT: child_subquery must come from select_ids_from_domain()
        to ensure record rules are applied.

        Example (members.sum(m, m.income) >= 10000):
            child_sql = select_ids_from_domain("res.partner", [])
            select_grouped_aggregate(
                "spp_group_membership", "m",
                child_sql,
                "group", "individual",
                "SUM", "income",
                ">=", 10000
            )
            -> SELECT m.group FROM spp_group_membership m
               WHERE m.individual IN (child_sql)  -- record rules applied
               GROUP BY m.group
               HAVING SUM(
                   (SELECT income FROM res_partner WHERE id = m.individual)
               ) >= 10000
        """

    # === Set Operations ===

    intersect(queries: list[SQL]) -> SQL
        """Combine queries with INTERSECT (for AND)."""

    union(queries: list[SQL]) -> SQL
        """Combine queries with UNION (for OR)."""
```

### 4.3 Operator Support Matrix

| Operator    | Supported | SQL Output          | Notes                |
| ----------- | --------- | ------------------- | -------------------- |
| `=`         | ✓         | `field = %s`        |                      |
| `!=`        | ✓         | `field != %s`       |                      |
| `>`         | ✓         | `field > %s`        |                      |
| `>=`        | ✓         | `field >= %s`       |                      |
| `<`         | ✓         | `field < %s`        |                      |
| `<=`        | ✓         | `field <= %s`       |                      |
| `in`        | ✓         | `field IN %s`       | Empty list → `1=0`   |
| `not in`    | ✓         | `field NOT IN %s`   | Empty list → `1=1`   |
| `= None`    | ✓         | `field IS NULL`     | Special handling     |
| `!= None`   | ✓         | `field IS NOT NULL` | Special handling     |
| `like`      | ✗         | -                   | Falls back to Python |
| `ilike`     | ✗         | -                   | Falls back to Python |
| `child_of`  | ✗         | -                   | Falls back to Python |
| `parent_of` | ✗         | -                   | Falls back to Python |

### 4.4 NULL Semantics

SQL NULL behavior differs from Python. Document explicitly:

| Expression        | Python              | SQL                 | Our Behavior      |
| ----------------- | ------------------- | ------------------- | ----------------- |
| `field = None`    | `field is None`     | `field IS NULL`     | Use IS NULL       |
| `field != None`   | `field is not None` | `field IS NOT NULL` | Use IS NOT NULL   |
| `SUM(NULL, 10)`   | N/A                 | `10`                | NULLs ignored     |
| `AVG([NULL, 10])` | N/A                 | `10.0`              | NULLs ignored     |
| `COUNT(NULL)`     | N/A                 | `0`                 | NULLs not counted |

**Rule**: Always test NULL cases in parity tests.

---

## 5. Plan-to-SQL Conversion

### 5.1 Conversion Table

| Plan Type               | SQL Support | Conversion Strategy                              |
| ----------------------- | ----------- | ------------------------------------------------ |
| `LeafDomain`            | ✓           | `select_ids_from_domain(model, domain)`          |
| `ExistsThrough`         | ✓           | `select_distinct_column()` with child subquery   |
| `CountThrough`          | ✓           | `select_grouped_count()` with HAVING             |
| `FieldAggregateThrough` | ✓           | `select_grouped_aggregate()` with CTE            |
| `MetricCompare`         | ✓\*         | Already implemented via `_metric_inselect_sql()` |
| `AND`                   | ✓           | `INTERSECT` of child SQLs                        |
| `OR`                    | ✓           | `UNION` of child SQLs                            |
| `NOT`                   | ✗           | Falls back to Python                             |
| `AggMetricCompare`      | ✗           | Falls back to Python                             |
| `CoverageRequire`       | ✗           | Falls back to Python                             |

\*MetricCompare uses SQL when metric cache is fresh.

### 5.2 Conversion Pseudocode

```
plan_to_sql(model, plan) -> SQL | None:
    """Convert QueryPlan to SQL. Returns None if not possible."""

    match plan:

        case LeafDomain(model, domain):
            if plan.model != model:
                return None  # Cross-model reference
            return builder.select_ids_from_domain(model, domain)

        case ExistsThrough(through_model, parent_field, link_field, child_model, child_plan, default_domain):
            # Build child filter SQL (with record rules)
            child_sql = None
            if child_plan:
                child_domain = plan_to_domain(child_model, child_plan)
                if requires_execution(child_domain):
                    return None
                child_sql = builder.select_ids_from_domain(child_model, child_domain)
                if child_sql is None:
                    return None

            # Build WHERE clause for through table
            where_parts = []
            for (field, op, value) in default_domain:
                term_sql = builder.term("m", field, op, value)
                if term_sql is None:
                    return None  # Unsupported operator
                where_parts.append(term_sql)

            if child_sql:
                where_parts.append(SQL("m.{link_field} IN {child_sql}"))

            where = builder.where_and(where_parts)
            return builder.select_distinct_column(through_model, "m", parent_field, where)

        case CountThrough(through_model, parent_field, link_field, child_model, child_plan, op, rhs, default_domain):
            # Similar to ExistsThrough, but with GROUP BY and HAVING
            child_sql = build_child_sql(child_model, child_plan)
            if child_sql is None and child_plan:
                return None

            where_parts = build_default_domain_sql(default_domain)
            if where_parts is None:
                return None

            if child_sql:
                where_parts.append(SQL("m.{link_field} IN {child_sql}"))

            where = builder.where_and(where_parts)
            return builder.select_grouped_count(
                through_model, "m", parent_field,
                where, op, rhs
            )

        case FieldAggregateThrough(through_model, parent_field, link_field, child_model, child_plan, agg_type, agg_field, op, rhs, default_domain):
            # Build child subquery with record rules
            child_domain = plan_to_domain(child_model, child_plan) if child_plan else []
            child_sql = builder.select_ids_from_domain(child_model, child_domain)
            if child_sql is None:
                return None

            where_parts = build_default_domain_sql(default_domain)
            if where_parts is None:
                return None

            # Build aggregate query using child subquery
            return builder.select_grouped_aggregate(
                through_model, "m",
                child_sql,
                parent_field, link_field,
                agg_type, agg_field,
                op, rhs
            )

        case MetricCompare(metric, subject_var, period_key, params, op, rhs):
            # Already implemented in _exec_metric with SQL path
            # Check if cache is fresh
            status = metric_cache_status(metric, period_key)
            if status == "fresh":
                return metric_inselect_sql(metric, period_key, op, rhs)
            return None  # Cache not fresh, use Python

        case AND(nodes):
            sqls = []
            for node in flatten_and(nodes):
                sql = plan_to_sql(model, node)
                if sql is None:
                    return None  # One failure = all Python
                sqls.append(sql)
            return builder.intersect(sqls)

        case OR(nodes):
            sqls = []
            for node in nodes:
                sql = plan_to_sql(model, node)
                if sql is None:
                    return None
                sqls.append(sql)
            return builder.union(sqls)

        case _:
            return None  # Unsupported plan type
```

### 5.3 SQL Generation Examples

**Example 1: Simple EXISTS**

```
Expression: members.exists(m, age_years(m.birthdate) < 5)
Plan: ExistsThrough(child_plan=LeafDomain([("birthdate", ">", "2019-12-07")]))

SQL:
    SELECT DISTINCT m."group"
    FROM spp_group_membership m
    WHERE m.is_ended = false
      AND m.individual IN (
          SELECT res_partner.id FROM res_partner
          WHERE res_partner.birthdate > '2019-12-07'
            AND res_partner.company_id IN (1)  -- record rule
            AND res_partner.active = true       -- record rule
      )
```

**Example 2: COUNT with threshold**

```
Expression: members.count(m, m.income > 0) >= 2
Plan: CountThrough(child_plan=LeafDomain([("income", ">", 0)]), op=">=", rhs=2)

SQL:
    SELECT m."group"
    FROM spp_group_membership m
    WHERE m.is_ended = false
      AND m.individual IN (
          SELECT res_partner.id FROM res_partner
          WHERE res_partner.income > 0
            AND res_partner.company_id IN (1)
            AND res_partner.active = true
      )
    GROUP BY m."group"
    HAVING COUNT(*) >= 2
```

**Example 3: SUM aggregation**

```
Expression: members.sum(m, m.income) >= 10000
Plan: FieldAggregateThrough(agg_type="SUM", agg_field="income", op=">=", rhs=10000)

SQL:
    WITH allowed_members AS (
        SELECT id, income FROM res_partner
        WHERE company_id IN (1) AND active = true  -- record rules
    )
    SELECT m."group"
    FROM spp_group_membership m
    JOIN allowed_members c ON c.id = m.individual
    WHERE m.is_ended = false
    GROUP BY m."group"
    HAVING SUM(c.income) >= 10000
```

**Example 4: Combined AND**

```
Expression: members.exists(m, true) AND status = 'active'
Plan: AND([ExistsThrough(...), LeafDomain([("status", "=", "active")])])

SQL:
    (
        SELECT DISTINCT m."group" FROM spp_group_membership m
        WHERE m.is_ended = false
    )
    INTERSECT
    (
        SELECT res_partner.id FROM res_partner
        WHERE res_partner.status = 'active'
          AND res_partner.company_id IN (1)
          AND res_partner.active = true
    )
```

**Example 5: MetricCompare (cache fresh)**

```
Expression: metric('income_level') >= 3
Plan: MetricCompare(metric="income_level", op=">=", rhs=3)

SQL (when cache fresh):
    SELECT DISTINCT fv.subject_id
    FROM spp_indicator_value fv
    WHERE fv.company_id = 1
      AND fv.metric = 'income_level'
      AND fv.subject_model = 'res.partner'
      AND fv.period_key = 'default'
      AND fv.error_code IS NULL
      AND (fv.expires_at IS NULL OR fv.expires_at > NOW())
      AND (fv.value_json::numeric) >= 3
```

---

## 6. Executor Changes

### 6.1 Updated `compile_and_preview()`

```
compile_and_preview(model, expr, limit=50) -> dict:
    """Compile CEL expression and return preview results.

    Returns:
        count: Total matching records (via search_count, not len(ids))
        preview_ids: First N matching IDs (via search with limit)
        path: "sql" | "python" | "domain"
        warnings: List of warnings (e.g., "Using Python path, may be slow")
        explain: Human-readable explanation
        domain: Final Odoo domain used
    """

    plan, explain = translate(expr)
    warnings = []

    # Try SQL path first
    sql = plan_to_sql(model, plan)

    if sql is not None:
        # SQL path - scales to millions
        domain = and_domains(base_domain, [("id", "in", sql)])
        path = "sql"
    else:
        # Check if simple domain (no execution needed)
        domain, requires_exec = plan_to_domain(model, plan)

        if not requires_exec:
            # Simple domain path
            domain = and_domains(base_domain, domain)
            path = "domain"
        else:
            # Python fallback - warn about scale
            reason = get_python_fallback_reason(plan)
            warnings.append(f"Using Python path: {reason}. May be slow for large datasets.")

            ids = execute_plan_python(plan)
            domain = and_domains(base_domain, [("id", "in", ids)])
            path = "python"

    # Get count efficiently (never materialize all IDs)
    count = search_count(domain)

    # Get preview IDs only
    preview_ids = search(domain, limit=limit).ids

    return {
        "count": count,
        "preview_ids": preview_ids,
        "path": path,
        "warnings": warnings,
        "explain": explain,
        "domain": domain,
    }
```

### 6.2 New `compile_for_batch()`

```
compile_for_batch(model, expr, batch_size=5000) -> Iterator[list[int]]:
    """Compile expression and yield batches of matching IDs.

    For processing millions of records without memory exhaustion.
    Uses cursor-based pagination (keyset pagination).

    Yields:
        Lists of IDs, each up to batch_size length

    Example:
        for batch_ids in executor.compile_for_batch("res.partner", expr):
            process_batch(batch_ids)  # Process 5000 at a time
    """

    sql = plan_to_sql(model, plan)

    if sql is not None:
        domain = and_domains(base_domain, [("id", "in", sql)])
    else:
        # For Python path, execute once and paginate results
        ids = execute_plan_python(plan)
        for i in range(0, len(ids), batch_size):
            yield ids[i:i+batch_size]
        return

    # Cursor-based pagination for SQL path
    last_id = 0
    while True:
        batch_domain = and_domains(domain, [("id", ">", last_id)])
        batch = search(batch_domain, limit=batch_size, order="id")

        if not batch:
            break

        yield batch.ids
        last_id = batch.ids[-1]

        if len(batch) < batch_size:
            break
```

### 6.3 New `compile_count_only()`

```
compile_count_only(model, expr) -> dict:
    """Get count of matching records without loading any IDs.

    Most efficient method when you only need the count.

    Returns:
        count: Number of matching records
        path: "sql" | "python" | "domain"
        warnings: List of warnings
    """

    sql = plan_to_sql(model, plan)

    if sql is not None:
        domain = and_domains(base_domain, [("id", "in", sql)])
        count = search_count(domain)
        return {"count": count, "path": "sql", "warnings": []}

    # Python fallback
    ids = execute_plan_python(plan)
    return {
        "count": len(ids),
        "path": "python",
        "warnings": ["Count required Python execution"]
    }
```

---

## 7. API Changes

### 7.1 Response Format Changes

**Current Response**:

```python
{
    "domain": [...],
    "count": 12345,
    "ids": [1, 2, 3, ..., 12345],  # ALL IDs - memory problem!
    "explain": "..."
}
```

**New Response**:

```python
{
    "domain": [...],
    "count": 12345,                    # From search_count()
    "preview_ids": [1, 2, 3, ..., 50], # Only first N
    "path": "sql",                     # Execution path used
    "warnings": [],                    # Any warnings
    "explain": "...",
}
```

### 7.2 Breaking Changes

| Change                                     | Migration                             |
| ------------------------------------------ | ------------------------------------- |
| `ids` renamed to `preview_ids`             | Update callers to use new field name  |
| `preview_ids` contains max N items         | Use `compile_for_batch()` for all IDs |
| `count` may differ from `len(preview_ids)` | Use `count` field for total           |

### 7.3 Deprecation Strategy

1. **Phase 1**: Add new fields, keep `ids` as alias for `preview_ids`
2. **Phase 2**: Log deprecation warning when `ids` accessed
3. **Phase 3**: Remove `ids` field

---

## 8. Testing Strategy

### 8.1 Unit Tests for SQL Builder

```
TestSQLBuilderTerm:
    test_term_equals_value
    test_term_equals_false
    test_term_equals_none_is_null
    test_term_not_equals_value
    test_term_not_equals_none_is_not_null
    test_term_greater_than
    test_term_greater_equal
    test_term_less_than
    test_term_less_equal
    test_term_in_list
    test_term_in_empty_list_returns_false
    test_term_not_in_list
    test_term_not_in_empty_list_returns_true
    test_term_like_returns_none
    test_term_ilike_returns_none
    test_term_escapes_field_names
    test_term_parameterizes_values

TestSQLBuilderSelect:
    test_select_ids_includes_record_rules
    test_select_ids_includes_company_filter
    test_select_ids_includes_active_filter
    test_select_distinct_column
    test_select_grouped_count
    test_select_grouped_aggregate_sum
    test_select_grouped_aggregate_avg

TestSQLBuilderSetOps:
    test_intersect_two_queries
    test_intersect_multiple_queries
    test_intersect_single_returns_single
    test_union_queries
```

### 8.2 Parity Tests (SQL vs Python)

```
TestSQLPythonParity:
    """Every expression must produce identical results in both paths."""

    def assert_paths_equal(expression, test_data):
        # Force SQL path
        sql_result = compile_with_sql(expression)

        # Force Python path (mock plan_to_sql to return None)
        python_result = compile_with_python(expression)

        # Must match exactly
        assert sorted(sql_result.ids) == sorted(python_result.ids)
        assert sql_result.count == python_result.count

    test_parity_simple_domain
    test_parity_exists_basic
    test_parity_exists_with_filter
    test_parity_count_equals
    test_parity_count_greater_than
    test_parity_count_less_than
    test_parity_sum_aggregation
    test_parity_avg_aggregation
    test_parity_and_combination
    test_parity_or_combination
    test_parity_complex_nested
    test_parity_with_null_values
    test_parity_empty_results
```

### 8.3 Edge Case Tests

```
TestEdgeCases:
    # NULL handling
    test_null_in_filtered_field
    test_null_in_aggregated_field
    test_null_birthdate_age_filter
    test_all_nulls_in_sum_returns_null

    # Boundaries
    test_zero_matching_records
    test_exactly_one_match
    test_count_exactly_threshold
    test_count_one_below_threshold
    test_count_one_above_threshold
    test_household_zero_members
    test_household_one_member

    # Empty data
    test_empty_membership_table
    test_empty_child_filter_results
    test_empty_in_list

    # Large data (mocked)
    test_preview_limited_to_n
    test_count_without_loading_ids
    test_batch_iterator_pagination
```

### 8.4 Security Tests

```
TestRecordRules:
    test_sql_respects_company_filter
    test_sql_respects_active_filter
    test_sql_respects_custom_record_rule
    test_multi_company_user_sees_own_company_only
    test_aggregation_excludes_restricted_records

TestSQLInjection:
    test_field_names_escaped
    test_values_parameterized
    test_operators_validated
    test_table_names_escaped
```

### 8.5 Performance Tests

```
TestPerformance:
    test_sql_generation_under_100ms
    test_preview_response_under_2s_for_1m_records
    test_memory_bounded_during_batch
    test_count_only_does_not_load_ids
```

---

## 9. Implementation Phases

### Phase 1: Critical Fixes (2-3 weeks)

**Goals**: Fix memory issue, fix operator support, establish testing framework.

**Deliverables**:

1. SQL Builder module with `term()`, `where_and()`, `select_ids_from_domain()`
2. Fix `compile_and_preview()` to use `search_count()` + `search(limit=N)`
3. Add all operator support (!=, >, <, >=, <=, in, not in)
4. Update `_exists_to_sql()` and `_count_to_sql()` to use builder
5. Parity test framework (10+ tests)
6. Security tests (5+ tests)

**Success Criteria**:

- Memory usage < 100MB for any result set size
- All operators work correctly
- SQL path = Python path for all tested expressions

### Phase 2: Comprehensive Testing (2-3 weeks)

**Goals**: Full test coverage, edge case handling, documentation.

**Deliverables**:

1. 25+ parity tests covering all expression types
2. 15+ edge case tests (NULL, boundaries, empty)
3. Performance benchmarks
4. Update specification with findings
5. Fix bugs discovered during testing

**Success Criteria**:

- > 90% code coverage on SQL generation
- All edge cases handled
- Documentation complete

### Phase 3: Advanced Features (2-3 weeks)

**Goals**: FieldAggregateThrough SQL, batch API, observability.

**Deliverables**:

1. `_aggregate_to_sql()` for SUM, AVG, MIN, MAX
2. `compile_for_batch()` iterator API
3. `compile_count_only()` for efficient counting
4. Logging and metrics
5. Performance optimization

**Success Criteria**:

- Aggregations use SQL path
- Batch processing works for 1M+ records
- Clear observability into execution paths

---

## 10. Configuration

### 10.1 System Parameters

```python
# ir.config_parameter keys and defaults

"cel.sql_enabled": "1"
    # Master switch for SQL path
    # "0" = always use Python (for debugging)
    # "1" = try SQL first, fall back to Python

"cel.preview_limit": "50"
    # Default limit for preview_ids

"cel.batch_size": "5000"
    # Default batch size for compile_for_batch()

"cel.log_sql_queries": "0"
    # Log generated SQL for debugging
    # "0" = off, "1" = on
```

### 10.2 Feature Detection

```
is_sql_supported(plan) -> tuple[bool, str]:
    """Check if plan can use SQL path.

    Returns:
        (True, "") if SQL is supported
        (False, reason) if SQL not supported

    Examples:
        (True, "")
        (False, "NOT expressions not supported in SQL")
        (False, "MetricCompare requires fresh cache")
        (False, "LIKE operator not supported in SQL")
    """
```

---

## 11. Observability

### 11.1 Logging

```
# SQL path used
[CEL SQL] path=sql expr="members.exists(...)"

# Python fallback with reason
[CEL SQL] path=python expr="..." reason="NOT expression not supported"

# Performance warning
[CEL PERF] path=python expr="..." count=150000 warning="Large result set"

# Debug: generated SQL (when cel.log_sql_queries=1)
[CEL DEBUG] sql="SELECT DISTINCT m.group FROM..."
```

### 11.2 Response Metadata

Every response includes:

```python
{
    "path": "sql" | "python" | "domain",
    "warnings": ["string", ...],
    "sql_supported": True | False,
    "sql_unsupported_reason": "..." | None,
}
```

---

## 12. Migration Guide

### 12.1 For API Consumers

**Before**:

```python
result = service.compile_expression(expr, profile)
all_ids = result["ids"]  # Could be millions!
for id in all_ids:
    process(id)
```

**After**:

```python
# For preview (UI display)
result = service.compile_expression(expr, profile)
count = result["count"]  # Total count
preview = result["preview_ids"]  # First 50

# For batch processing
for batch in executor.compile_for_batch(model, expr):
    for id in batch:
        process(id)

# For count only
result = executor.compile_count_only(model, expr)
count = result["count"]
```

### 12.2 Backwards Compatibility

- `result["ids"]` will continue to work but returns only preview (first N)
- Log deprecation warning when accessed
- Full removal in next major version

---

## 13. Appendix

### A. Database Compatibility

| Database         | INTERSECT | UNION | CTE | Status                 |
| ---------------- | --------- | ----- | --- | ---------------------- |
| PostgreSQL 12+   | ✓         | ✓     | ✓   | Full support           |
| PostgreSQL 10-11 | ✓         | ✓     | ✓   | Full support           |
| MySQL 8.0+       | ✓         | ✓     | ✓   | Full support           |
| MySQL 5.7        | ✗         | ✓     | ✗   | Limited (no INTERSECT) |
| SQLite 3.8+      | ✓         | ✓     | ✓   | Not tested             |

**Note**: OpenSPP officially supports PostgreSQL only. MySQL compatibility is
best-effort.

### B. Memory Comparison

| Scenario               | Before             | After                |
| ---------------------- | ------------------ | -------------------- |
| 100K matches, preview  | 100K IDs in memory | 50 IDs in memory     |
| 1M matches, count only | 1M IDs in memory   | 0 IDs in memory      |
| 1M matches, batch      | 1M IDs in memory   | 5K IDs max at a time |

### C. Performance Expectations

| Operation             | 100K records | 1M records | 10M records |
| --------------------- | ------------ | ---------- | ----------- |
| Count (SQL)           | < 100ms      | < 500ms    | < 2s        |
| Preview 50 (SQL)      | < 200ms      | < 1s       | < 3s        |
| Full batch (iterator) | ~5s          | ~30s       | ~5min       |
| Python fallback       | < 500ms      | 5-30s      | OOM risk    |

### D. Glossary

| Term             | Definition                                                   |
| ---------------- | ------------------------------------------------------------ |
| **SQL path**     | Expression fully converted to SQL subquery                   |
| **Python path**  | Expression executed in Python, IDs materialized              |
| **Domain path**  | Simple expression converted to Odoo domain without execution |
| **Record rules** | Odoo's row-level security (ir.rule)                          |
| **CTE**          | Common Table Expression (WITH clause)                        |
| **Parity test**  | Test comparing SQL and Python results for equality           |
