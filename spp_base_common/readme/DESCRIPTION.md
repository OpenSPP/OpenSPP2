Foundation module that aggregates OpenSPP core dependencies and provides phone number validation, menu icon customization, and base user role configuration. Acts as the primary dependency for implementation-specific base modules, ensuring consistent phone validation rules and UI theming across the platform.

### Key Capabilities

- Define configurable phone validation rules with digit count and prefix requirements
- Automatically validate phone numbers on create/write against active validation rules
- Customize menu icons for Registry, Apps, Settings, and standard Odoo modules
- Configure global and local registrar user roles with implied permissions
- Auto-populate partner phone field from structured phone number records

### Key Models

| Model                  | Description                                         |
| ---------------------- | --------------------------------------------------- |
| `spp.phone.validation` | Configurable phone validation rule (prefix, digits) |

**Extensions:**
- `spp.phone.number` - Adds automatic validation on save
- `res.partner` - Adds phone auto-population from phone_number_ids
- `ir.module.module` - Adds menu icon update on module install

### Configuration

After installing:

1. Menu icons (Registry, Apps, Settings) update automatically during installation
2. Global/local registrar roles are configured with implied permissions via data files
3. Create phone validation rules programmatically or via technical views (no standalone menu)

### UI Location

**No standalone menu.** Phone validation configuration is accessible through:
- Technical views (debug mode) via Settings > Technical > Database Structure > Models
- Registry main menu gets custom OpenSPP icon
- Apps and Settings menus get custom OpenSPP icons

### Security

| Group                                | Access                                |
| ------------------------------------ | ------------------------------------- |
| `base.group_system`                  | Full CRUD on phone validation         |
| `spp_registry.group_registry_read`   | Read-only on phone validation         |
| `spp_registry.group_registry_write`  | Read/Write (no create/delete)         |
| `spp_registry.group_registry_create` | Read/Create (no write/delete)         |

Additional access rules grant registry groups appropriate permissions on `res.partner`, `spp.phone.number`, `spp.registry.id`, `spp.registry.relationship`, `spp.id.type`, and technical models.

### Extension Points

- Override `_onchange_phone_validation()` in `spp.phone.number` to customize validation logic
- Extend `ICON_MAP` in `ir.module.module` to add menu icons for additional modules
- Inherit global/local role definitions in `data/global_roles.xml` and `data/local_roles.xml`

### Dependencies

`base`, `spp_user_roles`, `spp_hide_menus_base`, `spp_base_setting`, `spp_registry`, `spp_security`
