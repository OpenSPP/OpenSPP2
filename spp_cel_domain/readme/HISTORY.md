### 19.0.2.1.1

- fix(executor): probe for the legacy metric evaluation service by capability, not by model name. `_exec_metric` and the aggregate-metric path took the presence of `spp.indicator` in the registry to mean the retired `spp_indicators` service (with `evaluate()`) was installed; OpenSPP2's `spp_indicator` reuses that model name for an unrelated configuration model, so wherever it is installed every `metric()` over a variable whose cache was not fresh raised `AttributeError` inside the executor and the whole expression compiled to an error instead of the documented graceful empty result. Both sites now fall back to the SQL fast path when no service exposes `evaluate()` (#443)

### 19.0.2.1.0

- feat(sql): compile CEL ternary expressions to SQL CASE via `to_sql_case`, with `case_when`/`comparison` builders and a right-associative ternary parsing fix
- fix(translator): smart operator label lookup is read-only — never creates vocabulary records or uses `sudo()` during expression compilation
- test(translator): add coverage for the CEL translation cache helpers

### 19.0.2.0.0

- Initial migration to OpenSPP2
