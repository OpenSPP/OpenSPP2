No-code builder for creating custom change request types without writing Python or XML. Allows program staff to configure simple field-based change requests with approval workflows through a three-step wizard. Dynamically generates detail models, field mappings, form views, and access rights for each CR type.

### Key Capabilities

- Create custom change request types through a three-step wizard (naming, field selection, approval configuration)
- Dynamically generate `x_spp_cr_detail_*` models and `ir.model.fields` records at runtime when activating a CR type
- Map fields from `res.partner` to detail model fields, supporting char, text, date, selection, many2one, and other types
- Manage lifecycle through draft/active/inactive states with validation checks and deactivation impact warnings
- Configure approval groups and auto-apply settings per CR type
- Add or modify field mappings on active types; changes sync to detail models and form views automatically

### Key Models

| Model                                  | Description                                                    |
| -------------------------------------- | -------------------------------------------------------------- |
| `spp.studio.change.request.type`       | Studio-created CR type definition with lifecycle tracking      |
| `spp.studio.cr.field.mapping`          | Field mapping from `res.partner` to CR detail model            |
| `spp.cr.detail.generic`                | Generic detail template model (unused; types generate x_*)    |
| `x_spp_cr_detail_*` (dynamically)      | Auto-generated detail models for each activated CR type        |

### Configuration

After installing:

1. Navigate to **Studio > Forms & Fields > Change Requests**
2. Click **Create** or use the wizard to define a new CR type
3. Select fields from `res.partner` to expose in the change request form
4. Configure approval group and auto-apply settings
5. Activate the type to generate the detail model and make it available to users

### UI Location

- **Menu**: Studio > Forms & Fields > Change Requests
- **Wizard**: Three-step builder for guided CR type creation
- **Detail Forms**: Generated dynamically at `/web#model=x_spp_cr_detail_*`

### Security

| Group                                    | Access                                         |
| ---------------------------------------- | ---------------------------------------------- |
| `spp_studio.group_studio_viewer`         | Read CR types and mappings                     |
| `spp_studio.group_studio_editor_officer` | Read/Write/Create on CR types and mappings (no delete on CR types) |
| `spp_studio.group_studio_manager`        | Full CRUD                                      |

Detail models use `spp_change_request_v2` groups (user, validator, manager) with create disabled to prevent manual record creation.

### Extension Points

- Inherit `spp.studio.change.request.type` and override `_prepare_cr_type_vals()` to customize generated CR type configuration
- Override `_build_detail_form_arch()` to customize the generated form view XML structure
- Extend `spp.studio.cr.field.mapping._prepare_detail_field_vals()` to add custom field properties or domain filters

### Dependencies

`spp_studio`, `spp_change_request_v2`, `spp_registry`, `spp_audit`
