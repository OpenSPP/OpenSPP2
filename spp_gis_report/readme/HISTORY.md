### 19.0.2.1.0

- feat: metric disaggregation in GIS reports (breakdown dimensions, report helpers, wizard support) (re-land from #76; uses the spp_metric_service breakdown API).
- BREAKING (GeoJSON payload): disaggregation output moved from a nested `properties.disaggregation` object to flat `disagg_<dimension>_<value>` properties, with interpretation metadata under `metadata.disaggregation`. External consumers of `/api/v2/GISReport/.../geojson` (e.g. QGIS styles) that read the old nested key must be updated.
- BREAKING (model fields): the boolean `disaggregate_by_gender`/`disaggregate_by_age`/`disaggregate_by_disability` fields are removed in favor of `dimension_ids`; existing configurations are migrated automatically on upgrade (see migrations/19.0.2.1.0).

### 19.0.2.0.1

- fix(security): grant `group_gis_report_user` to spp_user_roles' Global Program Manager role so the OP#951 menu audit expectation (Program Manager sees GIS Reports) is preserved once the GIS Reports menu root is gated.
- fix(views): gate the "GIS Reports" top-level menu (`menu_gis_report_root`) on `group_gis_report_user`. Previously visible to every logged-in user; the OP#951 audit requires several roles to NOT see it (Registry Viewer, Global Finance, Global Support, Global Support Manager, Local Support, Global Registrar, Local Registrar, CR roles).

### 19.0.2.0.0

- Initial migration to OpenSPP2
