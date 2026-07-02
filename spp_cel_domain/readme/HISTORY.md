### 19.0.2.1.0

- feat(sql): compile CEL ternary expressions to SQL CASE via `to_sql_case`, with `case_when`/`comparison` builders and a right-associative ternary parsing fix
- fix(translator): smart operator label lookup is read-only — never creates vocabulary records or uses `sudo()` during expression compilation
- test(translator): add coverage for the CEL translation cache helpers

### 19.0.2.0.0

- Initial migration to OpenSPP2
