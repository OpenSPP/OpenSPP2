Humanitarian Exchange Language (HXL) integration for OpenSPP data interoperability. Provides a registry of standard HXL hashtags and attributes, tools for creating export profiles with HXL tagging, and extends CEL variables with HXL mapping capabilities. Enables OpenSPP to exchange data with humanitarian coordination systems using standardized HXL tagging conventions.

### Key Capabilities

- Registry of HXL 1.1 standard hashtags organized by category (geographic, population, activity, indicator, etc.)
- Registry of HXL attributes for data disaggregation (gender, age group, population type, etc.)
- Export profile definition for model-specific column mappings with HXL tags
- HXL tag composition from hashtag and attributes (e.g., #affected+f+children)
- Integration with CEL variables for import/export behavior configuration
- Validation of HXL tag format (hashtag starts with #, attributes start with +)

### Key Models

| Model                            | Description                                                    |
| -------------------------------- | -------------------------------------------------------------- |
| `spp.hxl.tag`                    | Registry of HXL hashtags (e.g., #affected, #adm2, #indicator) |
| `spp.hxl.attribute`              | Registry of HXL attributes (e.g., +f, +children, +code)       |
| `spp.hxl.export.profile`         | Export template defining model and column mapping with HXL tags  |
| `spp.hxl.export.profile.column`  | Column definition with field path and HXL tag assignment      |
| `spp.cel.variable` (extended)    | CEL variable with HXL hashtag, attributes, and import/export behavior |

### Configuration

After installing:

1. Navigate to **Custom > HXL > Configuration > HXL Hashtags** to view or add hashtags
2. Navigate to **Custom > HXL > Configuration > HXL Attributes** to view or add attributes
3. Create export profiles at **Custom > HXL > Export Profiles** specifying:
   - Target model for export
   - Column definitions with field paths
   - HXL tag assignment (manual or structured via hashtag + attributes)
4. For CEL variables, navigate to **Custom > Studio > Logic Variables** and use the HXL Mapping tab to define:
   - HXL hashtag and attributes for the variable
   - Import action (map to field, create event, store as variable, or skip)
   - Export inclusion preference

### UI Location

- **Menu**: Custom > HXL (main menu)
- **Configuration**: Custom > HXL > Configuration (HXL Hashtags, HXL Attributes)
- **Export Profiles**: Custom > HXL > Export Profiles
- **CEL Variable Extension**: Custom > Studio > Logic Variables > HXL Mapping tab

### Security

| Group                            | Access    |
| -------------------------------- | --------- |
| `base.group_user`                | Read      |
| `spp_security.group_spp_admin`   | Full CRUD |

### Extension Points

- Inherit `spp.hxl.export.profile` and override export logic to implement custom HXL export formats
- Extend `spp.hxl.tag` or `spp.hxl.attribute` to add domain-specific HXL tags (set `is_standard=False`)
- Inherit `spp.cel.variable` to customize HXL import/export behavior based on `hxl_import_action` field

### Dependencies

`spp_security`, `spp_cel_domain`, `spp_studio`, `spp_vocabulary`
