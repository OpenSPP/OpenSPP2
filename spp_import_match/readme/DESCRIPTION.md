Extends Odoo's base import functionality to match incoming records against existing data during bulk imports. Prevents duplicate creation by comparing imported rows to database records using configurable field combinations. Supports overwriting matched records and asynchronous processing for large datasets.

### Key Capabilities

- Define matching rules per model using field combinations to identify existing records
- Match on sub-fields within related records (e.g., household ID within individual)
- Apply conditional matching rules only when specific imported values are present
- Skip duplicate creation or update existing records when matches are found
- Process imports with more than 100 records asynchronously using `job_worker`
- Clear one2many/many2many associations before update to prevent duplicate entries

### Key Models

| Model                     | Description                                              |
| ------------------------- | -------------------------------------------------------- |
| `spp.import.match`        | Matching rule configuration for a specific model         |
| `spp.import.match.fields` | Individual fields used in a rule, supports sub-fields    |

### Configuration

After installing:

1. Navigate to **Registry > Configuration > Import Match**
2. Create a new matching rule and select the target model (e.g., `res.partner`)
3. Add one or more fields to match on (e.g., national ID, or first name + date of birth)
4. Enable **Overwrite Match** to update existing records when matches are found
5. For conditional matching, enable **Is Conditional** on a field and specify the expected imported value

### UI Location

- **Menu**: Registry > Configuration > Import Match
- **Import Dialog**: Matching applies automatically during CSV import via the standard Odoo import interface
- **Queue Jobs**: Registry > Queue Jobs > Jobs (to monitor asynchronous imports)

### Security

| Group                          | Access    |
| ------------------------------ | --------- |
| `spp_security.group_spp_admin` | Full CRUD |

### Extension Points

- Override `spp.import.match._match_find()` to customize matching logic for specific use cases
- Override `spp.import.match._usable_rules()` to filter which rules apply based on context
- Inherits `base.load()` to inject matching logic into all model imports

### Dependencies

`base`, `spp_base_common`, `base_import`, `job_worker`, `spp_security`
