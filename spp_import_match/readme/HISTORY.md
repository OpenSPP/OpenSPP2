### 19.0.2.0.2

- chore(views): hide the conditional-gate columns (`Is Conditional`, `Condition Field`, `Condition Value`) from the match-rule fields list — the schema and matching-engine wiring stay in place, but no current import flow uses the gate, so the columns are kept out of the UI until a real use case lands.

### 19.0.2.0.1

- fix(matching): add a `condition_field_id` Many2one column to `spp.import.match.fields` and rewrite the matching loop so conditional rows act as pure gates — never added to the DB search domain. Renames the IMPORTED VALUE column heading to **Condition Value**. Fixes the case where a CSV-only metadata column (e.g. `data_source`) was being injected into the search domain and causing zero matches.

### 19.0.2.0.0

- Initial migration to OpenSPP2
