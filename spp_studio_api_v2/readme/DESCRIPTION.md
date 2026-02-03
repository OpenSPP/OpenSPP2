Bridge module that exposes Studio custom fields and CEL variables through API v2. Auto-installs when both `spp_studio` and `spp_api_v2` are present. Studio fields are automatically registered to API extensions when activated, and API endpoints enable discovery of field schemas and variable metadata for external integrations.

### Key Capabilities

- Automatically register Studio custom fields to API extensions (`studio-individual` and `studio-group`) when activated
- Expose field definitions with JSON Schema validation rules, selection options, and visibility conditions
- List available CEL variables with metadata including value type, source type, and period granularity
- Retrieve cached variable values for Individual/Group resources with support for historical periods
- Parse incoming API extension data (CodeableConcept, ISO dates) into Odoo field values for create/update operations
- Monkey-patch IndividualService and GroupService to handle extension writes and include variable values in responses

### Key Models

| Model                                 | Description                                                    |
| ------------------------------------- | -------------------------------------------------------------- |
| `spp.studio.api.individual.mixin`     | Service methods for Individual API extension and variable data |
| `spp.studio.api.group.mixin`          | Service methods for Group API extension and variable data      |
| `spp.studio.field` (extended)         | Adds `api_exposed` flag and auto-registration hooks            |
| `fastapi.endpoint` (extended)         | Mounts Studio router on API v2 endpoint                        |

### API Endpoints

- **GET /Studio/fields**: List active Studio custom fields with configuration
- **GET /Studio/fields/{technical_name}/schema**: Get JSON Schema validation rules for a specific field
- **GET /Studio/variables**: List available CEL variables with metadata
- **GET /Studio/variables/{resource_type}/{identifier}**: Get cached variable values for an Individual or Group

All endpoints require `studio:read` scope.

### Configuration

After installing:

1. Studio fields created in **Studio > Forms & Fields > Custom Fields** are automatically registered to API extensions when activated
2. Set `api_exposed=False` on a Studio field to exclude it from API exposure
3. API extensions are defined in `data/api_extension_data.xml` as `studio-individual` and `studio-group`

### UI Location

No dedicated UI. Field registration happens automatically when Studio fields are activated.

### Security

| Group                                | Access                                                   |
| ------------------------------------ | -------------------------------------------------------- |
| `spp_api_v2.group_api_v2_read`       | Read on service mixins                                   |
| `spp_api_v2.group_api_v2_write`      | Read/Write on service mixins                             |
| `spp_api_v2.group_api_v2_create`     | Read/Write/Create on service mixins (no delete)          |

API authorization uses scope-based authentication (`studio:read` scope), not Odoo group checks.

### Extension Points

- Override `_convert_to_odoo()` in ExtensionWriteService to add custom field type conversions
- Override `compute_variable_value()` in VariableValueService to add custom computation logic
- Add models to `SAFE_LOOKUP_MODELS` (ExtensionWriteService) or `SAFE_SOURCE_MODELS` (VariableValueService) to enable lookups/computation

### Dependencies

`spp_api_v2`, `spp_studio`, `spp_cel_domain`
