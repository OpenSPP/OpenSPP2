Controls visibility of non-OpenSPP navigation menus by modifying ir.ui.menu group assignments. Automatically hides predefined menus from standard Odoo modules during installation and provides UI for manual toggle. Stores original group assignments to enable reversible hide/show operations.

### Key Capabilities

- Track menu visibility state and preserve original group assignments in configuration records
- Hide menus by replacing group_ids with `group_hide_menus_user` (only users in this group see hidden menus)
- Restore menus by reverting to original group_ids
- Auto-hide 15 predefined menus during module installation via `ir.module.module.next()` hook
- Manual toggle via list view with hide/show action buttons

### Key Models

| Model           | Description                                                      |
| --------------- | ---------------------------------------------------------------- |
| `spp.hide.menu` | Stores menu reference, state (show/hide), and original group_ids |

### Configuration

After installing, the module automatically hides menus from: `project_todo`, `mail`, `spreadsheet_dashboard`, `project`, `mass_mailing`, `survey`, `hr`, `calendar`, `contacts`, `account`, `event`, `stock`, `utm`, `fastapi`, `queue_job`.

To manually configure:

1. Navigate to **Settings > Users & Companies > Hidden Menus**
2. Click **Create** to add a menu to track
3. Use **Hide Menu** or **Show Menu** buttons to toggle visibility

### UI Location

- **Menu**: Settings > Users & Companies > Hidden Menus (requires Technical Features group)

### Security

| Group                                       | Access    |
| ------------------------------------------- | --------- |
| `base.group_system`                         | Full CRUD |
| `spp_hide_menus_base.group_hide_menus_user` | See menus hidden from other users (assigned via privilege system) |

### Extension Points

- Inherit `ir.module.module` and extend `MENU_APP` dictionary to add custom menus to auto-hide list
- Inherit `spp.hide.menu` to add custom metadata or hide/show logic

### Dependencies

`base`, `spp_security`
