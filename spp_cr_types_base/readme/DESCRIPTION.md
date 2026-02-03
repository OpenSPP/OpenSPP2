Defines three foundational change request types for updating registrant information. Provides data configurations for editing individual profiles, group profiles, and managing identification documents. All types are Studio-editable and use the apply strategies defined in the parent module.

### Key Capabilities

- **Edit Individual Information**: Updates personal data (name, birthdate, gender), contact information (phone, email), and address fields using field mapping strategy
- **Edit Group Information**: Updates group/household name, contact information, and address using field mapping strategy
- **Update ID Document**: Adds, updates, or removes identification documents using custom application logic with operation selection (add/update/remove)
- **Field Mapping Configuration**: Pre-configured mappings between detail model fields and target registrant fields for automatic data transfer
- **Studio Customization**: All CR types are marked as editable and cloneable in Studio for implementation-specific requirements

### Key Models

| Model                           | Description                                      |
| ------------------------------- | ------------------------------------------------ |
| `spp.cr.detail.edit_individual` | Detail form for individual information changes   |
| `spp.cr.detail.edit_group`      | Detail form for group/household information      |
| `spp.cr.detail.update_id`       | Detail form for ID document operations           |
| `spp.change.request.type`       | CR type configurations (defined in parent)       |
| `spp.change.request.type.mapping` | Field mappings for field_mapping strategy      |

### Configuration

After installing:

1. Navigate to **Change Requests > Configuration > Change Request Types**
2. Review the three pre-configured types: Edit Individual Information, Edit Group Information, Update ID Document
3. Optionally customize field mappings by clicking into each type and editing the Mappings tab
4. Clone any type via Studio to create domain-specific variants

### UI Location

- **CR Type Selection**: Types appear in the creation wizard at **Change Requests > New Request**
- **Configuration**: Change Requests > Configuration > Change Request Types
- **Detail Forms**: Accessed when creating or editing a change request of the corresponding type

### Security

| Group                                  | Access                              |
| -------------------------------------- | ----------------------------------- |
| `spp_change_request_v2.group_cr_user`  | Read/write/create detail models (no delete) |
| `spp_change_request_v2.group_cr_manager` | Full CRUD on detail models        |

### Extension Points

- Clone any base type via Studio to create domain-specific variants (e.g., "Edit Farmer Profile")
- Add custom fields to detail models via Studio; field mappings auto-discover new fields in dropdown
- Inherit `spp.cr.apply.update_id` and override `apply()` method to customize ID document application logic
- Mark types as `is_studio_editable=False` in inherited modules to prevent runtime modification

### Dependencies

`spp_change_request_v2`
