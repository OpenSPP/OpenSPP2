Starter bundle for Social Protection Management Information System (SP-MIS) deployments. Extends `spp_starter_social_registry` with program management, approval workflows, and service delivery capabilities. Adds optional registry access control, enforced on the server, to restrict registrant editing to administrators.

### Key Capabilities

- **Bundle Management**: Installs social registry foundation plus program management modules in a single deployment
- **Starter Type Configuration**: Sets system identifier to "sp_mis" for deployment classification
- **Registry Access Control**: Optional restriction withholding create, write and delete on registrant records from non-admin users
- **Server-Side Enforcement**: Applied in the access check every write passes through, so it holds over RPC and data import as well as in the web client — the New, Edit and Delete buttons disappear because Odoo stamps the view from the same access result

### Key Models

This module defines no models. It extends:

| Model         | Extension                                                                    |
| ------------- | ---------------------------------------------------------------------------- |
| `res.partner` | Withholds create, write and delete on registrant records from non-admin users |

The restriction is switched on and off from **Settings → Registry → General Settings**, which is where registry configuration now lives (OP#1009). This module keeps its own storage key, so its enforcement is unchanged.

### Configuration

After installing:

1. Navigate to **Settings > Registry > General Settings** (the SP-MIS section was folded into it — OP#1009)
2. Enable **Restrict Registry Edits to Admin Only** to enforce read-only registry access for non-admin users
3. When enabled, non-admin users can still read the registry, but creating, editing and deleting registrants is refused — and the corresponding buttons are not shown
4. Restriction applies only to `res.partner` views; program-related operations remain available based on role

### UI Location

- **Settings**: Settings > Registry > General Settings (registry access control toggle; changing it requires a Settings administrator)
- **Programs**: Inherited from `spp_programs` (Social Protection > Programs)
- **Service Points**: Inherited from `spp_service_points` via transitive dependency

### Implementation Details

The registry restriction uses:

- **Config Parameter**: `spp_starter.registry_admin_only_crud` (default: True), marked `noupdate` so an administrator's choice survives module upgrades
- **Access Check**: `res.partner._check_access` withholds create, write and unlink on records flagged `is_registrant`
- **Promotion Guard**: `write` refuses setting `is_registrant` on a plain contact, which would otherwise add a registrant in two allowed steps
- **Admin Check**: Users in `spp_security.group_spp_admin` bypass all restrictions
- **Scope**: Only registrant records are affected, so the Contacts app stays usable

### Included Modules

Everything from `spp_starter_social_registry` (registry, API, DCI, change requests) plus:

- `spp_programs` (includes `spp_service_points` as transitive dependency)
- `spp_approval`
- `spp_event_data`
- `spp_api_v2_cycles` (auto-installed when `spp_api_v2` + `spp_programs` are present)

### Dependencies

`spp_starter_social_registry`, `spp_programs`, `spp_approval`, `spp_event_data`
