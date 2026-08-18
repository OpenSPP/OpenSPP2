### 19.0.2.0.0

- Initial migration to OpenSPP2
- fix(analysis): `ExplainAnalyzer` no longer executes the statements it analyzes — non-SELECT
  statements get a plan-only `EXPLAIN` (previously captured INSERTs were re-executed under
  `EXPLAIN ANALYZE`, silently duplicating rows), and every analysis runs inside a savepoint so a
  failing EXPLAIN cannot abort the caller's transaction
- fix(tests): the ADR-008 variable-resolver suite actually runs now (its availability guard
  compared a falsy empty recordset and skipped every test); the concurrency test exercises the
  shared LRU cache without racing the test cursor
- fix(tests): studio validation targets the OpenSPP2 studio (`spp.studio.pack` models,
  `cel_expression`-based `logic_data` contract); the legacy `mode`/`conditions` schema is asserted
  absent
- fix(analysis): `QueryCapture` handles the `SQL` objects the Odoo 19 ORM passes to
  `Cursor.execute` (previously all ORM traffic was silently dropped and only hand-written string
  SQL was captured), passes through `log_exceptions` instead of raising `TypeError`, and restores
  the cursor's real `execute` on stop instead of shadowing it
- fix(analysis): `analyze_query` results carry an `analyzed` flag so plan-only (non-SELECT)
  results are distinguishable from instrumented clean runs
- test(analysis): unit coverage for the query-capture, slow-query-report and index-advisor helpers
- chore: performance thresholds calibrated to shared CI runners (order-of-magnitude regression
  guards, not tuning targets)

### 19.0.1.0.0

- Initial release (openspp-modules)
