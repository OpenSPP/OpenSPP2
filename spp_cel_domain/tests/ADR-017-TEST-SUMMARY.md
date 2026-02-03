# ADR-017 Variable Caching Strategy - Test Summary

## Overview

This document summarizes the test suite created for ADR-017: Variable Caching Strategy for Scale.

## Test Files Created/Modified

### 1. `test_data_cache_manager.py` (NEW)

**File**: `/spp_cel_domain/tests/test_data_cache_manager.py` **Test Class**: `TestDataCacheManager` **Test Count**: 17
tests

#### Coverage:

- **Pre-computation Tests** (6 tests)

  - `test_precompute_variable_ttl_strategy` - Verifies TTL cached variables are stored in spp.data.value
  - `test_precompute_variable_manual_strategy` - Verifies manual cached variables work correctly
  - `test_precompute_variable_none_strategy_fails` - Ensures non-cached variables fail pre-computation
  - `test_precompute_variable_empty_subject_ids` - Tests with empty subject lists
  - `test_precompute_variable_nonexistent` - Tests error handling for missing variables

- **Batch Pre-computation Tests** (4 tests)

  - `test_precompute_cached_variables_all` - Batch pre-computation of all cached variables
  - `test_precompute_cached_variables_specific_names` - Pre-compute specific variable subset
  - `test_precompute_cached_variables_empty_subjects` - Empty subject list handling
  - `test_precompute_cached_variables_no_cached_vars` - No cached variables scenario

- **Cache Invalidation Tests** (4 tests)

  - `test_invalidate_variable_specific_subjects` - Invalidate cache for specific subjects
  - `test_invalidate_variable_all_subjects` - Invalidate all cache entries for a variable
  - `test_invalidate_variable_specific_period` - Invalidate by period key
  - `test_invalidate_nonexistent_variable` - Handle invalidation of non-existent variable

- **Refresh Operations Tests** (2 tests)

  - `test_refresh_variable` - Refresh cached values for a variable
  - `test_refresh_variables_for_subject` - Refresh all variables for a subject

- **Session Cache Tests** (2 tests)
  - `test_session_cache_cleared` - Verify session cache can be cleared
  - `test_session_cache_stats` - Session cache statistics

### 2. `test_cel_variable_resolver.py` (NEW)

**File**: `/spp_cel_domain/tests/test_cel_variable_resolver.py` **Test Class**: `TestCELVariableResolverCaching` **Test
Count**: 13 tests

#### Coverage:

- **Cache Strategy Detection Tests** (8 tests)

  - `test_expand_cached_variable_emits_metric_ttl` - TTL variables emit metric() calls
  - `test_expand_cached_variable_emits_metric_manual` - Manual variables emit metric() calls
  - `test_expand_inline_variable_expands_cel_none_strategy` - None strategy expands inline
  - `test_expand_inline_variable_expands_cel_session_strategy` - Session strategy expands inline
  - `test_expand_mixed_cached_and_inline_variables` - Mixed variable types
  - `test_expand_nested_cached_variables` - Nested cached variables
  - `test_expand_constant_cached_variable` - Cached constants
  - `test_expand_field_cached_variable` - Cached field variables

- **Cache Info Analysis Tests** (3 tests)

  - `test_analyze_expression_caching` - Classify variables by cache strategy
  - `test_resolve_with_cache_info` - Expansion with cache metadata
  - `test_resolve_with_cache_info_no_cached_vars` - No cached variables scenario

- **Edge Cases** (2 tests)
  - `test_expand_variable_default_cache_strategy` - Default strategy handling
  - `test_cache_strategy_logging` - Logging verification

### 3. `test_cel_caching.py` (MODIFIED)

**File**: `/spp_cel_domain/tests/test_cel_caching.py` **Test Class**: `TestCELExecutorCacheLookup` (NEW class added)
**Test Count**: 7 new tests

#### Coverage:

- **Executor Cache Lookup Tests** (7 tests)
  - `test_metric_lookup_uses_data_value_table` - metric() uses spp.data.value for lookups
  - `test_metric_lookup_respects_period_key` - Period key handling
  - `test_metric_lookup_empty_cache_graceful` - Graceful empty cache handling
  - `test_metric_lookup_partial_cache_coverage` - Partial cache coverage
  - `test_metric_lookup_uses_sql_fast_path` - SQL fast path verification
  - `test_metric_multiple_variables_cache_lookup` - Multiple cached variables
  - `test_metric_lookup_with_comparison_operators` - Various comparison operators (==, >=, !=)

## Total Test Count

**37 new tests** covering ADR-017 implementation:

- 17 tests for Cache Manager
- 13 tests for Variable Resolver
- 7 tests for Executor Cache Lookup

## Running the Tests

### Run all ADR-017 tests:

```bash
./scripts/test_single_module.sh spp_cel_domain
```

### Run specific test classes:

```bash
# Cache Manager tests
pytest spp_cel_domain/tests/test_data_cache_manager.py -v

# Variable Resolver tests
pytest spp_cel_domain/tests/test_cel_variable_resolver.py -v

# Executor Cache Lookup tests (within test_cel_caching.py)
pytest spp_cel_domain/tests/test_cel_caching.py::TestCELExecutorCacheLookup -v
```

### Local development:

```bash
cd openspp-odoo-19-migration/
invoke test-spp-deps --modules=spp_cel_domain --skip=queue_job --mode=init --db-filter='^devel$'
```

## Test Data Setup

All tests use `CELTestDataMixin` from `/tests/common.py` to create isolated test data without relying on XML seed data.
Each test class:

- Creates unique test identifiers using timestamps
- Sets up test partners (beneficiaries)
- Clears caches before each test
- Uses TransactionCase for proper database rollback

## Key Testing Patterns

### 1. Cache Strategy Detection

Tests verify that the variable resolver correctly identifies cached variables and emits `metric()` calls instead of
inline CEL expansion.

```python
# TTL cached variable should emit metric()
result = resolver.expand_expression("cached_score > 50")
assert "metric('cached_score', me)" in result["expression"]

# Inline variable should expand CEL
result = resolver.expand_expression("inline_var > 5")
assert "r.income / 1000" in result["expression"]
```

### 2. Pre-computation Workflow

Tests verify the complete pre-computation workflow from variable definition to cache storage.

```python
# Create cached variable
var = Variable.create({
    "cache_strategy": "ttl",
    ...
})

# Pre-compute
result = cache_mgr.precompute_variable(var.name, subject_ids)
assert result["success"] == True

# Verify in spp.data.value
cached = DataValue.search([("variable_name", "=", var.name)])
assert len(cached) == len(subject_ids)
```

### 3. End-to-End Cache Lookup

Tests verify the complete flow from expression compilation to cache lookup.

```python
# Populate cache
DataValue.create({
    "variable_name": "test_metric",
    "value_json": {"value": 85},
    ...
})

# Execute expression (resolver → executor → cache lookup)
result = service.compile_expression("test_metric > 50")
assert result["valid"] == True
assert partner_id in result["preview_ids"]
```

## Coverage Goals

- ✅ Variable Resolver cache strategy detection
- ✅ Cache Manager pre-computation methods
- ✅ Cache Manager invalidation methods
- ✅ Cache Manager refresh methods
- ✅ Session cache management
- ✅ Executor metric() cache lookups
- ✅ SQL fast path verification
- ✅ Empty cache handling
- ✅ Partial cache coverage
- ✅ Multiple cached variables
- ✅ Period key handling

## ADR-017 Implementation Phase Coverage

### Phase 1: Variable Resolver Update ✅

- Tests verify `expand_expression()` checks `cache_strategy`
- Tests verify `metric('var_name', me)` emission for cached variables
- Tests verify inline expansion for non-cached variables

### Phase 2: Executor Update ✅

- Tests verify `_exec_metric()` queries `spp.data.value`
- Tests verify freshness checking works with new table
- Tests verify SQL fast path for cached variables

### Phase 3: Batch Pre-computation ✅

- Tests verify `precompute_variable()` method
- Tests verify `precompute_cached_variables()` batch method
- Tests verify cache invalidation methods

### Phase 4: Cache Manager Refactor ✅

- Tests verify `spp.data.cache.manager` functionality
- Tests verify session cache management
- Tests verify refresh operations

## Notes for Developers

1. **Test Isolation**: All tests use unique identifiers to avoid conflicts
2. **Cache Cleanup**: Each test clears caches in `setUp()` to ensure clean state
3. **Database Transactions**: Using `TransactionCase` ensures automatic rollback
4. **Logging**: Some tests verify debug logging for troubleshooting
5. **Edge Cases**: Tests cover empty caches, missing variables, partial coverage

## Related Documentation

- ADR-017: `/docs/architecture/decisions/ADR-017-variable-caching-strategy.md`
- Implementation: `spp_cel_domain/models/`
  - `cel_variable_resolver.py` (lines 262-276)
  - `cel_executor.py` (\_exec_metric, \_get_cache_table_info)
  - `data_evaluator.py` (renamed to spp.data.cache.manager)
- Cycle Hook: `spp_programs/models/managers/cycle_manager_base.py` (line 297)
