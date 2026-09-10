### 19.0.2.0.4

- chore(farmer_registry): the duplicate Farmer Registry Settings section is removed — the toggle it carried now lives in Registry Settings, and this module's storage key is written in step with it, so enforcement is unchanged (#1009)

### 19.0.2.0.3

- fix(farm): remove the farm membership-completeness warnings entirely — both the "No head member designated" and "No members linked to this group yet" banners, their "No Head Member" / "No Members" search filters, the `member_count` and head-member list columns, and the backing `has_head_member` / `member_count` computed fields. The head-member check misfired on farm groups that did have a head, and per #1113 no such warnings should be shown (#1113)

### 19.0.2.0.2

- fix(security): align Farm User / Farm Manager roles with the OP#951 menu audit — both farm roles now imply `spp_hazard.group_hazard_viewer` and `spp_gis_report.group_gis_report_user` so they retain Hazard and GIS Reports menu visibility once those menu roots are gated. Adds `spp_hazard` and `spp_gis_report` to module dependencies.

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the farm activities list on farm forms — removes the four empty placeholder rows Odoo 19 inserts on inline list-in-form views (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
