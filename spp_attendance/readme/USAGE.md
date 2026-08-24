### Syncing participants from a registry

The participant import (Settings > SPP Attendance Settings, used by the *Import Attendance*
wizard) is fully configuration-driven: an auth endpoint, a search endpoint, and JSON-path mappings
into the response. The shipped defaults target the SPDCI-style interface of a legacy
openspp-modules registry (`/oauth2/client/token` + `/registry/sync/search`).

To sync from an **OpenSPP2** registry instead, point the settings at the DCI server modules
(`spp_dci_server` + `spp_dci_server_social` must be installed on the registry instance):

| Setting | Value for an OpenSPP2 registry |
| --- | --- |
| Server URL | `https://<registry-host>` |
| Auth Endpoint | `/api/v2/spp/oauth/token` (spp_api_v2 client-credentials endpoint) |
| Import Endpoint | `/dci_api/v1/registry/sync/search` |

The JSON-path mappings (personal information, identifier, names, contact fields) must match the
DCI search response envelope of the target registry; adjust them from the defaults as needed.

### API access for external systems

1. Create client credentials under **Attendance > Configuration > API Clients**. The client secret
   is displayed **once** at creation (and on regeneration) — store it securely; only a hash is kept.
2. Obtain a token: `POST /auth/token` with `client_id`/`client_secret`.
3. Call the attendance endpoints with the token in the `Authorization` header (`Bearer` scheme).

Signing keys come from `spp_oauth` (Settings > General Settings > OpenSPP OAuth); the RSA keypair
must be configured before tokens can be issued.
