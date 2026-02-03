Dynamically adds custom fields to registrant profiles without code changes. Administrators create fields on `res.partner` following naming conventions, and the module automatically injects them into individual and group forms in organized sections. Supports field grouping and read-only indicator fields for program metrics.

### Key Capabilities

- Define custom fields with `x_cst_grp_*` (group) or `x_cst_indv_*` (individual) naming pattern
- Define read-only indicator fields with `x_ind_grp_*` or `x_ind_indv_*` naming pattern
- Organize fields into named groups with sequence-based ordering
- Automatically inject fields into registrant forms based on registrant type
- Display custom fields under "Additional Details" tab, indicators under "Indicators" tab

### Key Models

| Model                      | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `spp.custom.field.group`   | Groups custom fields for organized display in UI    |
| `ir.model.fields` (extend) | Adds `field_group_id` and `sequence` for field order |
| `res.partner` (extend)     | Dynamically injects custom fields into forms         |

### Configuration

After installing:

1. Create field groups via **Settings > Technical > Actions > Window Actions**, search for "Field Groups"
2. Specify target type (Individual or Group) and sequence for each group
3. Navigate to **Settings > Technical > Database Structure > Models**
4. Select **Contact (res.partner)** and create custom fields:
   - For group registrants: `x_cst_grp_fieldname` or `x_ind_grp_fieldname`
   - For individuals: `x_cst_indv_fieldname` or `x_ind_indv_fieldname`
5. Assign `field_group_id` and `sequence` to organize field display

### UI Location

- **Field Groups**: No menu defined; access via Settings > Technical > Actions > Window Actions
- **Custom fields**: Appear on registrant forms under "Additional Details" tab
- **Indicator fields**: Appear on registrant forms under "Indicators" tab (read-only)

### Security

| Group               | Access    |
| ------------------- | --------- |
| `base.group_user`   | Read      |
| `base.group_system` | Full CRUD |

### Extension Points

- Override `_inject_custom_pages()` to customize tab and field injection logic
- Override `_group_fields_by_group()` to modify field grouping and sorting
- Extend `spp.custom.field.group` to add metadata or classification fields

### Dependencies

`base`, `spp_registry`, `spp_security`
