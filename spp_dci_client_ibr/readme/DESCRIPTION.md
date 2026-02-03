Connects OpenSPP to Integrated Beneficiary Registry (IBR) systems for duplication checks via the DCI API. Queries external IBR endpoints to detect duplicate enrollments across programs, receives async callback responses, and verifies signatures using JWKS-based public key infrastructure.

### Key Capabilities

- Check registrants for duplicate enrollments in external IBR systems using DCI protocol
- Store duplication check results with match status, matched programs, and raw API responses
- Manage trusted IBR sender registries with automatic JWKS public key fetching
- Receive async search response callbacks at `/dci_api/ibr/on-search` endpoint
- Verify callback signatures using Ed25519 or RSA-256 algorithms
- Track duplication check lifecycle: ready → checking → completed/failed

### Key Models

| Model                       | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| `spp.dci.duplication.check` | Stores duplication check requests and results from IBR   |
| `spp.dci.ibr.sender`        | Registry of trusted IBR systems with public keys         |
| `fastapi.endpoint`          | Inherited to add IBR callback router to DCI API endpoint |

### Configuration

After installing:

1. Navigate to **Settings > Technical > DCI > Configuration > IBR Senders**
2. Create an IBR sender record with sender ID and JWKS URL
3. Click **Fetch Public Key** to retrieve the public key from the IBR's JWKS endpoint
4. Verify the algorithm field is populated (Ed25519 or RSA-256)

### UI Location

- **IBR Duplication Checks**: Settings > Technical > DCI > Activity Logs > IBR Duplication Checks
- **IBR Senders**: Settings > Technical > DCI > Configuration > IBR Senders
- **FastAPI Callbacks**: `/dci_api/ibr/on-search` and `/dci_api/ibr/on-subscribe`

### Security

| Group                                     | Model                       | Access           |
| ----------------------------------------- | --------------------------- | ---------------- |
| `spp_registry.group_registry_viewer`      | `spp.dci.duplication.check` | Read             |
| `spp_registry.group_registry_officer`     | `spp.dci.duplication.check` | Read/Write/Create (no delete) |
| `spp_registry.group_registry_manager`     | `spp.dci.duplication.check` | Full CRUD        |
| `base.group_system`                       | `spp.dci.ibr.sender`        | Full CRUD        |
| `base.group_user`                         | `spp.dci.ibr.sender`        | Read             |

### Extension Points

- Override `_process_ibr_search_result()` in `routers/callback.py` to customize result processing
- Inherit `spp.dci.duplication.check` to add domain-specific fields or validation
- Extend `fastapi.endpoint._get_fastapi_routers()` to add additional IBR-related routes
- Override `spp.dci.ibr.sender._jwk_to_pem()` to support additional key formats

### Dependencies

`spp_dci_client`, `spp_dci_server`, `spp_registry`
