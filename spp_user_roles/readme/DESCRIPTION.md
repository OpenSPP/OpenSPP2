Extends `base_user_role` to categorize roles as global or local, enabling area-based access control. Automatically synchronizes user security groups when roles are assigned. Protects essential system groups from removal during sync. Disables scheduled role updates in favor of manual UI-triggered updates.

### Key Capabilities

- Categorize roles as global (system-wide) or local (area-specific) via `role_type` selection field
- Automatically sync security groups when roles are assigned or updated via overridden `set_groups_from_roles()`
- Protect base system groups (user, portal, public, technical features) from accidental removal during sync
- Display assigned roles in user list view via computed stored Many2many field
- Manually trigger role synchronization via "Update User Roles" button on role form

### Key Models

| Model                 | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `res.users.role`      | Extended with `role_type` field and manual update action |
| `res.users.role.line` | Extended with related `role_type` field                  |
| `res.users`           | Extended with stored roles field and custom group sync   |

### Configuration

After installing:

1. Navigate to **Settings > Users & Companies > Users**
2. Open a user form and go to the "Roles & Access Rights" tab
3. Add role lines and set `role_type` to "Global" or "Local"
4. Groups are synchronized automatically when roles are saved
5. Use "Update User Roles" button on role form to manually trigger sync

### UI Location

- **User Management**: Settings > Users & Companies > Users (Roles & Access Rights tab)
- **Role Form**: Accessed from user's role lines with "Update User Roles" button
- **No standalone menu**: Extends existing Settings views, does not add new menu items

### Security

| Group                                  | Access                          |
| -------------------------------------- | ------------------------------- |
| `spp_user_roles.group_local_registrar` | Read users, roles, and role lines |
| `spp_security.group_spp_admin`         | Full CRUD on roles and role lines |

### Predefined Roles

**Global Roles** (system-wide access):

- System Admin, Registry Viewer, Global Finance, Global Program Manager, Global Registrar, Global Support, Global Support Manager

**Local Roles** (area-specific access):

- Local Registrar, Local Support

### Extension Points

- Override `set_groups_from_roles()` to customize which groups are protected from removal (currently protects `base.group_user`, `base.group_no_one`, `mail.group_mail_template_editor`, `base.group_portal`, `base.group_public`)
- Inherit `res.users.role` to add custom fields or selection values for `role_type`
- Extend `action_update_users()` to add custom logic during manual role synchronization

### Dependencies

`base`, `mail`, `spp_registry`, `base_user_role`, `spp_security`
