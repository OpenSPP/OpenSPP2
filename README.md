# OpenSPP

Open-source Social Protection Platform built on [Odoo 19](https://www.odoo.com/).

## Quick Start

```bash
# Clone this repository
git clone https://github.com/OpenSPP/OpenSPP2.git
cd OpenSPP2

# Start with Docker Compose
docker compose --profile ui up -d

# Access at http://localhost:8069 (admin/admin)
```

## External Dependencies

This repository requires additional OCA and third-party modules.
See [EXTERNAL_DEPENDENCIES.md](EXTERNAL_DEPENDENCIES.md) for details.
The Docker setup handles these automatically.

## Modules

This repository contains 67 Odoo modules:

- `endpoint_route_handler`
- `fastapi`
- `spp_alerts`
- `spp_api_v2`
- `spp_api_v2_change_request`
- `spp_api_v2_cycles`
- `spp_api_v2_data`
- `spp_api_v2_entitlements`
- `spp_api_v2_products`
- `spp_api_v2_service_points`
- `spp_api_v2_vocabulary`
- `spp_approval`
- `spp_area`
- `spp_area_hdx`
- `spp_audit`
- `spp_banking`
- `spp_base_common`
- `spp_base_setting`
- `spp_branding_kit`
- `spp_cel_domain`
- `spp_cel_event`
- `spp_cel_registry_search`
- `spp_cel_vocabulary`
- `spp_cel_widget`
- `spp_change_request_v2`
- `spp_claim_169`
- `spp_consent`
- `spp_cr_types_advanced`
- `spp_cr_types_base`
- `spp_custom_field`
- `spp_dci`
- `spp_dci_client`
- `spp_dci_client_crvs`
- `spp_dci_client_dr`
- `spp_dci_client_ibr`
- `spp_dci_server`
- `spp_demo`
- `spp_dms`
- `spp_drims`
- `spp_drims_sl`
- `spp_drims_sl_demo`
- `spp_event_data`
- `spp_gis`
- `spp_gis_report`
- `spp_gis_report_programs`
- `spp_grm`
- `spp_grm_demo`
- `spp_hazard`
- `spp_hide_menus_base`
- `spp_key_management`
- `spp_mis_demo_v2`
- `spp_programs`
- `spp_registry`
- `spp_registry_search`
- `spp_security`
- `spp_service_points`
- `spp_source_tracking`
- `spp_starter_social_registry`
- `spp_starter_sp_mis`
- `spp_studio`
- `spp_studio_api_v2`
- `spp_studio_change_requests`
- `spp_studio_events`
- `spp_user_roles`
- `spp_versioning`
- `spp_vocabulary`
- `theme_openspp_muk`

## License

LGPL-3. See [LICENSE](LICENSE) for details.
