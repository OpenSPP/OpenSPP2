Demo data generator for OpenSPP with Faker-based random registrant creation and fixed demo stories. Generates realistic individuals and groups with locale-specific data providers. Includes predefined personas for sales demos and training. Supports batch processing with queue_job for large datasets.

### Key Capabilities

- Generate random registrants using Faker library with locale-specific providers (Kenya, Laos, Sri Lanka)
- Create fixed demo stories with memorable names for repeatable demos (e.g., "Maria Santos", "Juan Dela Cruz")
- Generate IDs from regex patterns with validation and error logging
- Batch process large datasets using queue_job (configurable threshold)
- Configure percentages for IDs, GPS coordinates, and bank accounts
- Track generation failures with diagnostic logging
- Extend `res.country` with Faker locale and GPS boundaries
- Create demo user accounts (viewer, officer, supervisor, manager, admin)

### Key Models

| Model                              | Description                                           |
| ---------------------------------- | ----------------------------------------------------- |
| `spp.demo.data.generator`          | Main generator with configuration and batch controls  |
| `spp.demo.data.generation.log`     | Logs failed generation attempts with diagnostics      |
| `spp.demo.data.id.types`           | ID type configuration for individual/group generation |
| `spp.demo.data.bank.types`         | Bank type configuration for account generation        |
| `spp.apps.wizard`                  | Wizard for installing missing demo modules            |
| `spp.missing.module`               | Transient model for tracking missing modules          |

### Configuration

After installing:

1. Navigate to **Settings > General Settings > SPP Demo Data Generator Settings** to set defaults:
   - Number of groups
   - Members per group range
   - Batch size and queue job threshold
2. Access generator via action `spp_demo.action_demo_data_generator` (no standalone menu)
3. Configure Faker locales on country records via `faker_locale` field
4. Set GPS boundaries (`lat_min`, `lat_max`, `lon_min`, `lon_max`) on countries for coordinate generation

### UI Location

- **Action**: `spp_demo.action_demo_data_generator` (no standalone menu item)
- **Configuration**: Settings > General Settings > SPP Demo Data Generator Settings
- **Form tabs**: Generated Groups, Generated Individuals, ID Types, Bank Types, Generation Logs

### Security

| Group                                   | Access                                              |
| --------------------------------------- | --------------------------------------------------- |
| `base.group_system`                     | Full CRUD on all models                             |
| `spp_registry.group_registry_read`      | Read access to all models                           |
| `spp_registry.group_registry_write`     | Read/Write on generator and logs (delete ID/Bank types) |
| `spp_registry.group_registry_create`    | Read/Create access (delete ID/Bank types)           |

### Extension Points

- Override `_create_individual_story()`, `_create_farmer_story()`, `_create_household_story()` for custom story generation
- Add custom stories to `models/demo_stories.py` (`DEMO_STORIES` or `BACKGROUND_STORIES` lists)
- Extend `res.country` with `faker_locale` field for custom locale providers
- Use utility methods:
  - `create_individual_from_params(name, gender, age, extra_vals)` - Create individual without full generator session
  - `create_group_from_params(name, extra_vals)` - Create group from parameters
  - `lookup_gender_id(gender)` - Look up gender vocabulary code ID

### Dependencies

`base`, `spp_base_common`, `spp_registry`, `spp_vocabulary`, `queue_job`, `spp_security`

External Python dependency: `faker`
