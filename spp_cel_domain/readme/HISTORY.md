### 19.0.2.1.1

- fix(translator): `members.count(predicate)` now honours its predicate when compared. Both call styles are valid -- a single argument is the predicate with `m` implicit, two arguments are an explicit loop variable and predicate -- but the comparison path read the first argument as the loop variable either way and substituted a `True` predicate when there was no second one. `members.count(pred) > n` therefore counted every member, silently and without error, so every aggregate count variable (`child_count`, `elderly_count`, `working_age_count`) returned the household size and any program targeting on one matched every household. `exists()` was unaffected, which is why variables built on it kept working. Note an aggregate count nested inside arithmetic, as `dependency_ratio` is, still loses its predicate -- a separate path (#955)

### 19.0.2.1.0

- feat(sql): compile CEL ternary expressions to SQL CASE via `to_sql_case`, with `case_when`/`comparison` builders and a right-associative ternary parsing fix
- fix(translator): smart operator label lookup is read-only — never creates vocabulary records or uses `sudo()` during expression compilation
- test(translator): add coverage for the CEL translation cache helpers

### 19.0.2.0.0

- Initial migration to OpenSPP2
