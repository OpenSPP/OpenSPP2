### 19.0.2.0.1

- Upgrade to Production/Stable status
- Fix category to `OpenSPP/Configuration`
- Use `search_count()` in `get_paid_apps_count()` for efficiency
- Add proper JSON response content-type to `/openspp/about` endpoint
- Clean up outdated `requirements.txt` referencing Odoo 17
- Increase test coverage to 95%+ (utils, settings, controllers, HTTP endpoints)
- Update `readme/DESCRIPTION.md` to follow module description template
- Fix uninstall hook to clean up `spp.*` parameters (was using wrong `openspp.*` prefix)
- Remove global Apps menu override that forced OpenSPP filter on all users
- Scope CSS branding selectors to login page context
- Change `/openspp/about` endpoint from public to authenticated access
- Remove empty placeholder view files (`login_templates.xml`, `backend_customization.xml`)
- Remove missing `banner.png` reference from manifest
- Add CSRF justification comment on `/publisher-warranty` endpoint

### 19.0.2.0.0

- Initial migration to OpenSPP2
