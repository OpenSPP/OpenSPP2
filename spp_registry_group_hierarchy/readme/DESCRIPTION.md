Enables nested group structures by allowing registry groups to contain other groups as members, not just individuals. Extends the membership model to support parent-child group relationships with dynamic member filtering based on group type configuration.

### Key Capabilities

- Compute dynamic member domains that can include or exclude groups based on group type settings
- Display hierarchical terminology (Parent/Child) in membership forms instead of generic Group/Member labels
- Navigate to appropriate detail forms for both individual and group members via unified action
- Filter available members to prevent circular references (groups cannot be members of themselves)

### Key Models

| Model                  | Description                                                      |
| ---------------------- | ---------------------------------------------------------------- |
| `spp.group.membership` | Extended with `individual_domain` field and `open_member_form()` method |

### Configuration

No additional configuration required. The module extends existing membership functionality automatically. Group types determine member eligibility through the group type configuration in the base registry module.

### UI Location

- **Forms**: Extends the group membership form view with "Parent:" and "Child:" labels
- **Tab**: Group membership list on group forms shows hierarchical labels and member form button
- **No menu items**: This module only extends existing views from `spp_registry`

### Security

No new access control entries. Uses existing `spp.group.membership` permissions from parent modules.

### Extension Points

- Override `_compute_individual_domain()` to customize member filtering logic for different group type configurations
- Override `open_member_form()` to modify navigation behavior when opening member detail forms

### Dependencies

`spp_security`, `base`, `spp_registry`
