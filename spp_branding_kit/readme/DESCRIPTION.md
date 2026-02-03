Replaces Odoo branding with OpenSPP branding across the platform. Adds `/openspp` URL routing as an alias for `/odoo` routes, redirects telemetry to OpenSPP endpoints or disables it entirely, and customizes system messages, email signatures, and report footers. Works with `theme_openspp_muk` for visual styling.

### Key Capabilities

- URL routing: `/openspp/programs/123` works as an alias for `/odoo/programs/123`
- Telemetry control: redirect to OpenSPP endpoint or disable entirely via configuration
- Session branding: injects OpenSPP system name and version into web client session
- Email signatures: replaces default Odoo signature with OpenSPP branding
- Report customization: updates company report headers and footers with OpenSPP text
- Post-install debranding: disables Odoo brand promotion messages, update notification crons, and theme store menu
- Module filtering: adds "OpenSPP Apps" menu to filter and view OpenSPP-specific applications

### Key Models

This module does not introduce new models. It extends existing models:

| Model                 | Extension Purpose                                      |
| --------------------- | ------------------------------------------------------ |
| `res.users`           | Custom email signature, removes Odoo account URL       |
| `res.config.settings` | Adds branding and telemetry configuration fields       |
| `ir.http`             | Injects OpenSPP branding into web client session info  |
| `ir.module.module`    | Provides utility to count paid/proprietary apps        |

### Configuration

After installing:

1. Open the **Settings** app
2. Scroll to the **OpenSPP Branding** section (app card with OpenSPP icon)
3. Configure **System Name** (default: "OpenSPP Platform")
4. Set **Documentation URL** and **Support URL** for help links
5. Toggle **Display OpenSPP Branding** to show/hide "Powered by OpenSPP"
6. Configure telemetry: **Enable Telemetry** (redirects to OpenSPP endpoint) or disable
7. Set **Telemetry Endpoint** if redirecting (default: `https://telemetry.openspp.org`)

Post-install hook automatically disables Odoo brand promotion, module update notifications, and theme store menu.

### Menu Location

- **Apps > OpenSPP Apps** - View and filter OpenSPP-specific applications

### Security

This module does not define security groups or access rights. Configuration access follows standard Odoo settings permissions (requires `base.group_system` - Settings access).

### Extension Points

- Override `get_branding_config(env)` in `utils.py` to customize branding data injected into session
- Inherit `res.users` to further customize email signatures or user menu elements
- Inherit `ir.http.session_info()` to add custom branding keys to web client session
- Patch JavaScript router in `static/src/js/router_patch.js` to customize URL prefix beyond `/openspp`

### Dependencies

`spp_security`, `base`, `web`, `base_setup`, `theme_openspp_muk`
