### 19.0.2.0.3

- fix(farm): remove the "No head member designated" warning banner and its `has_head_member` check (banner, search filter, list column, and the computed field). The check misfired on farm groups that did have a head, and per #1113 no such warning should be shown. The "No Members" banner/filter are unchanged (#1113)

### 19.0.2.0.2

- fix(security): align Farm User / Farm Manager roles with the OP#951 menu audit — both farm roles now imply `spp_hazard.group_hazard_viewer` and `spp_gis_report.group_gis_report_user` so they retain Hazard and GIS Reports menu visibility once those menu roots are gated. Adds `spp_hazard` and `spp_gis_report` to module dependencies.

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the farm activities list on farm forms — removes the four empty placeholder rows Odoo 19 inserts on inline list-in-form views (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
