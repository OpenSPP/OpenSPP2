### 19.0.2.0.1

- fix(security): align Farm User / Farm Manager roles with the OP#951 menu audit — both farm roles now imply `spp_hazard.group_hazard_viewer` and `spp_gis_report.group_gis_report_user` so they retain Hazard and GIS Reports menu visibility once those menu roots are gated. Adds `spp_hazard` and `spp_gis_report` to module dependencies.

### 19.0.2.0.0

- Initial migration to OpenSPP2
