### 19.0.2.1.1

- fix(security): key metric cache lookups strictly by the requested params. The provider clause used to fall back to param-agnostic cache rows (`(provider, "")` and `("", "")`), so a parameterized `metric(..., arg=…)` predicate could be satisfied by an unparameterized/legacy cached value — silently selecting subjects by a less-specific value in eligibility/targeting/DCI-search flows. Reads are now keyed by the exact `params_hash` (both the freshness preflight and the SQL fast path), and the compute/refresh path re-caches under the correct params key.

### 19.0.2.1.0

- feat(sql): compile CEL ternary expressions to SQL CASE via `to_sql_case`, with `case_when`/`comparison` builders and a right-associative ternary parsing fix
- fix(translator): smart operator label lookup is read-only — never creates vocabulary records or uses `sudo()` during expression compilation
- test(translator): add coverage for the CEL translation cache helpers

### 19.0.2.0.0

- Initial migration to OpenSPP2
