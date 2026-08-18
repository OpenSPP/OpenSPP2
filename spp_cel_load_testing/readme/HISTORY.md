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
- test(analysis): unit coverage for the query-capture, slow-query-report and index-advisor helpers
- chore: performance thresholds calibrated to shared CI runners (order-of-magnitude regression
  guards, not tuning targets)

### 19.0.1.0.0

- Initial release (openspp-modules)
