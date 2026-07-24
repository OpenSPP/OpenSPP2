### 19.0.2.1.1

- fix: recognise `me` as a CEL context identifier. The resolver rewrites cached
  variables (and the DCI override rewrites dotted accessors) into
  `metric('<accessor>', me)` before identifiers are extracted; because `me` was
  missing from `CEL_CONTEXT_IDENTIFIERS`, `validate_expression` /
  `validate_formula_expression` wrongly reported valid expressions as
  `Undefined variables: me`. `me` is the individual record proxy in the eval
  context, so it is now a recognised context identifier.

### 19.0.2.1.0

- feat(sql): compile CEL ternary expressions to SQL CASE via `to_sql_case`, with `case_when`/`comparison` builders and a right-associative ternary parsing fix
- fix(translator): smart operator label lookup is read-only — never creates vocabulary records or uses `sudo()` during expression compilation
- test(translator): add coverage for the CEL translation cache helpers

### 19.0.2.0.0

- Initial migration to OpenSPP2
