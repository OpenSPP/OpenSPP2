### 19.0.2.1.2

- fix(security): add global `ir.rule` records on `spp.program.membership` and `spp.cycle.membership` that filter by `partner_id.area_id` against the user's `center_area_ids` (OP#989 round-2). The earlier Python `_prepare_domain` override on program memberships only caught `search_read` / `web_search_read` and missed counts (`search_count`, `read_group`), dropdowns (`name_search`), and related-field traversal — and cycle memberships had no filter at all. Both rules use a conditional domain that's a no-op for users with no center areas (global roles).

### 19.0.2.1.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the Programs and Entitlements lists on registrant forms and to Program Membership inline lines — removes the four empty placeholder rows Odoo 19 inserts on inline list-in-form views (#943).

### 19.0.2.0.11

- Fix `TypeError: 'NoneType' object is not iterable` when clicking **Enroll Eligible** on programs with at least 200 beneficiaries (async dispatch path)
- Mirror `get_beneficiaries` semantics in `_enroll_eligible_registrants_async`: when `state` is `None`, omit the state filter instead of crashing on `tuple(None)`

### 19.0.2.0.10

- Increase parallel-safe channel limits (cycle, eligibility_manager, program_manager) from 1 to 4
- Add serial `entitlement_approval` channel (limit=1) for fund balance safety
- Add serial `statistics_refresh` channel (limit=1) to prevent concurrent refresh storms
- Add `identity_key` to async job dispatchers to prevent duplicate submission on double-click

### 19.0.2.0.9

- Add context flags (`skip_registrant_statistics`, `skip_program_statistics`) to suppress expensive computed field recomputation during bulk operations
- Add `refresh_beneficiary_counts()` on program and `refresh_statistics()` on cycle for one-shot recomputation after bulk operations
- Replace `bool(rec.program_membership_ids)` with SQL query in `_compute_has_members`

### 19.0.2.0.8

- Replace OFFSET pagination with NTILE-based ID-range batching in all async job dispatchers
- Add `compute_id_ranges()` utility using PostgreSQL NTILE window function
- Add `min_id`/`max_id` support to `get_beneficiaries()` on program and cycle

### 19.0.2.0.7

- Bulk membership creation using raw SQL INSERT ON CONFLICT DO NOTHING for program and cycle memberships
- Replace per-record ORM creates in `_import_registrants` and `_add_beneficiaries` with bulk SQL path

### 19.0.2.0.6

- Remove unused entitlement_base_model.py (dead code, never imported)
- Fix manifest summary to remove marketing language
- Recover 5 orphaned test files and add core model, wizard, manager, payment, and fund tests (172 → 492 tests)

### 19.0.2.0.5

- Batch create entitlements and payments instead of one-by-one ORM creates

### 19.0.2.0.4

- Fetch fund balance once per approval batch instead of per entitlement

### 19.0.2.0.3

- Replace cycle computed fields (total_amount, entitlements_count, approval flags) with SQL aggregation queries

### 19.0.2.0.2

- Add composite indexes for frequent query patterns on entitlements and program memberships

### 19.0.2.0.1

- Replace Python-level uniqueness checks with SQL UNIQUE constraints for program membership, cycle membership, and entitlement codes
- Add pre-migration script to deduplicate existing data before constraint creation

### 19.0.2.0.0

- Initial migration to OpenSPP2
