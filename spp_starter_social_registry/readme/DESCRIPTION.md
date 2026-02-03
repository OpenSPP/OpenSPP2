Bundle module that installs the complete OpenSPP Social Registry stack in a single operation. Combines registry management, REST API, DCI integrations, change requests, and no-code configuration tools. Sets the deployment type to `social_registry` via configuration parameter. Use this for deployments tracking individuals and groups without program enrollment or entitlement management.

### Key Capabilities

- One-click installation of all Social Registry dependencies
- Automatically configures `spp_starter.registry_type` parameter to `social_registry`
- Bundles core registry, API, DCI clients, change requests, and no-code tools
- Installs async job processing infrastructure via `queue_job`

### Configuration

After installing:

1. The system parameter `spp_starter.registry_type` is set to `social_registry` automatically
2. Access registry features through bundled modules (see menus in `spp_registry`, `spp_api_v2`, `spp_dci_client`)
3. Refer to individual module documentation for configuration steps

### Use Cases

- National Social Registries tracking population demographics
- Humanitarian registration systems without program management
- Civil registration databases requiring external data synchronization
- ID management systems as standalone deployments

For SP-MIS deployments with program enrollment and entitlements, use `spp_starter_sp_mis` instead.

### Bundled Modules

**Core Registry:**
`spp_registry`, `spp_registry_search`, `spp_security`, `spp_area`, `spp_vocabulary`

**Data Management:**
`spp_consent`, `spp_source_tracking`, `queue_job`

**Change Requests:**
`spp_change_request_v2`, `spp_cr_types_base`

**Expression Engine:**
`spp_cel_domain`, `spp_studio`

**API V2:**
`spp_api_v2`, `spp_api_v2_data` (auto-installs `spp_api_v2_vocabulary`, `spp_api_v2_change_request`)

**DCI Integration:**
`spp_dci_client`, `spp_dci_client_crvs`, `spp_dci_client_ibr`, `spp_dci_client_dr`

### Dependencies

`spp_registry`, `spp_registry_search`, `spp_security`, `spp_area`, `spp_vocabulary`, `spp_consent`, `spp_source_tracking`, `queue_job`, `spp_change_request_v2`, `spp_cr_types_base`, `spp_cel_domain`, `spp_studio`, `spp_api_v2`, `spp_api_v2_data`, `spp_dci_client`, `spp_dci_client_crvs`, `spp_dci_client_ibr`, `spp_dci_client_dr`
