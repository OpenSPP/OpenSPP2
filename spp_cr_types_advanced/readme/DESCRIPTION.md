Installs eight advanced change request types that use custom Python apply strategies for complex registry operations. Types include membership management (add/remove/transfer members, change head of household), group operations (create/split groups), registrant lifecycle (exit/deactivate), and data quality (merge duplicates). All types are marked as non-editable via Studio to prevent modification of Python-only logic.

### Key Capabilities

- **Membership operations**: Add member, remove member, change head of household, transfer member between groups
- **Group operations**: Create new groups, split households into separate groups
- **Registrant lifecycle**: Exit and deactivate registrants from the system
- **Data quality**: Merge duplicate registrant records with full data consolidation
- All types use `apply_strategy='custom'` with Python models that cannot be modified via Studio

### Models Secured by This Module

This module does not define models. It provides data records for `spp.change.request.type` and security rules for detail/apply models defined in `spp_change_request_v2`:

| Detail Model                      | Apply Model                      | Purpose                          |
| --------------------------------- | -------------------------------- | -------------------------------- |
| `spp.cr.detail.add_member`        | `spp.cr.apply.add_member`        | Add new member to group          |
| `spp.cr.detail.remove_member`     | `spp.cr.apply.remove_member`     | Remove member from group         |
| `spp.cr.detail.change_hoh`        | `spp.cr.apply.change_hoh`        | Change head of household         |
| `spp.cr.detail.transfer_member`   | `spp.cr.apply.transfer_member`   | Transfer member between groups   |
| `spp.cr.detail.exit_registrant`   | `spp.cr.apply.exit_registrant`   | Deactivate registrant            |
| `spp.cr.detail.create_group`      | `spp.cr.apply.create_group`      | Create new group/household       |
| `spp.cr.detail.split_household`   | `spp.cr.apply.split_household`   | Split household into two groups  |
| `spp.cr.detail.merge_registrants` | `spp.cr.apply.merge_registrants` | Merge duplicate registrant records |

### Configuration

After installing:

1. Navigate to **Change Requests > Configuration > Change Request Types**
2. Eight advanced CR types are now available with icons and descriptions
3. Each type is marked `is_studio_editable=False` and `is_system_type=True` with a `locked_reason` explaining why Studio editing is disabled

### UI Location

- **Configuration**: Change Requests > Configuration > Change Request Types
- **Create Requests**: Forms accessible from registrant profiles based on `target_type` (individual/group/both)
- **Type Codes**: `add_member`, `remove_member`, `change_hoh`, `transfer_member`, `exit_registrant`, `create_group`, `split_household`, `merge_registrants`

### Security

| Group                                    | Access                              |
| ---------------------------------------- | ----------------------------------- |
| `spp_change_request_v2.group_cr_user`    | Read/Write/Create (no delete)       |
| `spp_change_request_v2.group_cr_manager` | Full CRUD including delete          |

Security rules apply to all eight detail models.

### Extension Points

- Override apply strategies in `spp_change_request_v2/strategies/*.py` to customize behavior
- Inherit detail models in `spp_change_request_v2/details/*.py` to add fields
- Clone type definitions if `is_studio_cloneable` is enabled to create variants

### Dependencies

`spp_change_request_v2`
