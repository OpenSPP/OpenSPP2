Bundle module that installs the OpenSPP Disability Registry stack in a single operation. It combines registry management, REST API, change requests, no-code configuration tools, and the disability assessment registry — everything from the Social Registry starter **except** the DCI client integrations. Sets the deployment type to `disability_registry` via configuration parameter.

### Key Capabilities

- One-click installation of the Disability Registry dependencies
- Automatically configures `spp_starter.registry_type` to `disability_registry`
- Bundles core registry, API, change requests, no-code tools, and `spp_disability_registry`
- Installs async job processing infrastructure via `job_worker`

### Configuration

After installing:

1. The system parameter `spp_starter.registry_type` is set to `disability_registry` automatically
2. Configure disability assessment behaviour under **Settings → Disability Registry**
3. Refer to individual module documentation for further configuration

### Use Cases

- Disability registries capturing WG/CFM assessments, impairment classification, and support needs
- Deployments that need the registry + API + change-request stack without DCI client synchronization

For deployments that also need DCI client integration, use `spp_starter_social_registry`.

### Bundled Modules

**Core Registry:**
`spp_registry`, `spp_registry_search`, `spp_security`, `spp_area`, `spp_vocabulary`

**Data Management:**
`spp_consent`, `spp_source_tracking`, `job_worker`

**Change Requests:**
`spp_change_request_v2`, `spp_cr_types_base`

**Expression Engine & No-Code UI:**
`spp_cel_domain`, `spp_studio`

**API V2:**
`spp_api_v2`, `spp_api_v2_data` (auto-installs `spp_api_v2_vocabulary`, `spp_api_v2_change_request`)

**Disability Registry:**
`spp_disability_registry`

### Dependencies

`spp_registry`, `spp_registry_search`, `spp_security`, `spp_area`, `spp_vocabulary`, `spp_consent`, `spp_source_tracking`, `job_worker`, `spp_change_request_v2`, `spp_cr_types_base`, `spp_cel_domain`, `spp_studio`, `spp_api_v2`, `spp_api_v2_data`, `spp_disability_registry`
