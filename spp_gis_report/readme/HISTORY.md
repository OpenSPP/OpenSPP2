### 19.0.2.1.0

- feat: metric disaggregation in GIS reports (breakdown dimensions, report helpers, wizard support) (re-land from #76; uses the spp_metric_service breakdown API).

### 19.0.2.0.1

- fix(security): grant `group_gis_report_user` to spp_user_roles' Global Program Manager role so the OP#951 menu audit expectation (Program Manager sees GIS Reports) is preserved once the GIS Reports menu root is gated.
- fix(views): gate the "GIS Reports" top-level menu (`menu_gis_report_root`) on `group_gis_report_user`. Previously visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Registry Viewer, Global Finance, Global Support, Global Support Manager, Local Support, Global Registrar, Local Registrar, CR roles).

### 19.0.2.0.0

- Initial migration to OpenSPP2
