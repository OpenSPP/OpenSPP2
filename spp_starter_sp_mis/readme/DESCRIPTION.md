Starter bundle for Social Protection Management Information System (SP-MIS) deployments. Extends `spp_starter_social_registry` with program management, approval workflows, and service delivery capabilities. Adds optional client-side registry access control to restrict registrant editing to administrators.

### Key Capabilities

- **Bundle Management**: Installs social registry foundation plus program management modules in a single deployment
- **Starter Type Configuration**: Sets system identifier to "sp_mis" for deployment classification
- **Registry Access Control**: Optional JavaScript-based restriction that makes registrant forms read-only for non-admin users
- **Client-Side Enforcement**: Patches `FormController` and `ListController` to hide Create/Edit/Delete buttons and force readonly mode

### Key Models

This module defines no models. It extends:

| Model                  | Extension                                       |
| ---------------------- | ----------------------------------------------- |
| `res.config.settings`  | Adds `is_registry_admin_only_crud` boolean field |

### Configuration

After installing:

1. Navigate to **Settings > SP-MIS Settings**
2. Enable **Restrict Registry Edits to Admin Only** to enforce read-only registry access for non-admin users
3. When enabled, non-admin users see registrant forms in readonly mode with hidden create/edit/delete buttons
4. Restriction applies only to `res.partner` views; program-related operations remain available based on role

### UI Location

- **Settings**: Settings > SP-MIS Settings (registry access control toggle)
- **Programs**: Inherited from `spp_programs` (Social Protection > Programs)
- **Service Points**: Inherited from `spp_service_points` via transitive dependency

### Implementation Details

The registry restriction uses:

- **Config Parameter**: `spp_starter.registry_admin_only_crud` (default: True)
- **JSON-RPC Endpoint**: `/spp_starter_sp_mis/registry_restriction` checks restriction status
- **JavaScript Patches**: Modifies `FormController` and `ListController` for `res.partner` model
- **Admin Check**: Users in `spp_security.group_spp_admin` bypass all restrictions
- **MutationObserver**: Monitors DOM changes to re-apply restrictions dynamically

### Included Modules

Everything from `spp_starter_social_registry` (registry, API, DCI, change requests) plus:

- `spp_programs` (includes `spp_service_points` as transitive dependency)
- `spp_approval`
- `spp_event_data`
- `spp_api_v2_cycles` (auto-installed when `spp_api_v2` + `spp_programs` are present)

### Dependencies

`spp_starter_social_registry`, `spp_programs`, `spp_approval`, `spp_event_data`
