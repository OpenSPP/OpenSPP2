Extends Odoo's base import functionality to match incoming records against existing data during bulk imports. Prevents duplicate creation by comparing imported rows to database records using configurable field combinations. Supports overwriting matched records and asynchronous processing for large datasets.

### Key Capabilities

- Define matching rules per model using field combinations to identify existing records
- Match on sub-fields within related records (e.g., `parent_id/name`)
- Apply conditional matching rules only when a specific imported value is present
- Skip duplicate creation or update existing records when matches are found
- Split imports exceeding 100 rows into chunks and process asynchronously via `job_worker`
- Strip falsy one2many/many2many values on write to prevent duplicate relational entries

### Key Models

| Model                     | Description                                           |
| ------------------------- | ----------------------------------------------------- |
| `spp.import.match`        | Matching rule configuration for a specific model      |
| `spp.import.match.fields` | Individual field in a rule, with optional sub-field    |

### Configuration

After installing:

1. Navigate to **Registry > Configuration > Import Match**
2. Create a matching rule and select the target model (e.g., `res.partner`)
3. Add one or more fields to match on (e.g., national ID, or first name + date of birth)
4. Enable **Overwrite Match** to update existing records when matches are found
5. For conditional matching, enable **Is Conditional** on a field and set the expected imported value

### UI Location

- **Menu**: Registry > Configuration > Import Match
- **Import Dialog**: Select a matching rule and overwrite option from the import sidebar

### Security

| Group                          | Access    |
| ------------------------------ | --------- |
| `spp_security.group_spp_admin` | Full CRUD |

### Extension Points

- Override `spp.import.match._match_find()` to customize matching logic
- Override `spp.import.match._usable_rules()` to filter which rules apply based on context
- Overrides `base.load()` to inject matching into all model imports
- Overrides `base.write()` to strip falsy one2many/many2many values

### Dependencies

`base`, `spp_base_common`, `base_import`, `job_worker`, `spp_security`
