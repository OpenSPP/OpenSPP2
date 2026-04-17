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
