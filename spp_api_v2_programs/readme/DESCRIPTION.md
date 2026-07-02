Extends OpenSPP API V2 with REST endpoints for **Programs** and **Program Memberships**. This module was split out of `spp_api_v2` so that the base API module no longer depends on `spp_programs` — deployments that don't use programs (e.g. a registry-only Social Registry) can ship the API without installing the Programs stack.

It auto-installs whenever both `spp_api_v2` and `spp_programs` are present, so program API functionality is unchanged for deployments that use programs.

### Key Capabilities

- **Program endpoints**: read and search programs (`/api/v2/spp/Program`)
- **Program Membership endpoints**: read, search, create, and update beneficiary enrollments (`/api/v2/spp/ProgramMembership`)
- **Advanced filtering**: `/_filters` and `/_search` endpoints for both resources, registered into the shared API V2 filter framework
- **OAuth scopes**: the `program` and `program_membership` client-scope resources (defined in `spp_api_v2`) gate access

### UI Location

No standalone menu. Endpoints are available under the API V2 app:

- `/api/v2/spp/Program`, `/api/v2/spp/Program/{identifier}`
- `/api/v2/spp/ProgramMembership`, `/api/v2/spp/ProgramMembership/{identifier}`

### Dependencies

`spp_api_v2`, `spp_programs`
