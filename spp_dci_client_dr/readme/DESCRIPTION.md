Connects OpenSPP to Disability Registry (DR) systems via DCI API. Queries PWD (Person with Disability) status, retrieves functional assessment scores, and caches disability information locally. Supports both synchronous queries and asynchronous callback notifications from DR systems.

### Key Capabilities

- Query disability status from remote DR systems using DCI client
- Cache disability data in local records with sync status tracking (synced, stale, error)
- Receive async search response callbacks via FastAPI endpoints
- Verify callback signatures using Ed25519 or RSA-256 algorithms
- Match DR responses to OpenSPP registrants by UIN, DRN, or National ID
- Refresh cached data manually or programmatically

### Key Models

| Model                       | Description                                                                   |
| --------------------------- | ----------------------------------------------------------------------------- |
| `spp.dci.disability.status` | Cached disability data: PWD flag, disability types, functional scores, raw data |
| `spp.dci.dr.sender`         | Trusted DR registry entries with sender_id, public keys, and JWKS endpoints    |

### Configuration

After installing:

1. Navigate to **Settings > Technical > DCI > Configuration > DR Senders**
2. Create a DR sender record with `sender_id` matching the remote DR system
3. Configure the JWKS URL (e.g., `https://dr.example.org/.well-known/jwks.json`)
4. Click **Fetch Public Key** to retrieve and store the DR's public key for signature verification

To query disability status programmatically:

```python
from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

dr_service = DRService(env, data_source_code='dr_main')
disability_data = dr_service.get_disability_status(partner)
is_pwd = dr_service.is_pwd(partner)
```

### UI Location

- **Menu**: Settings > Technical > DCI > Activity Logs > Disability Status
- **Configuration**: Settings > Technical > DCI > Configuration > DR Senders
- **Callback Endpoints**: `/dci_api/dr/on-search`, `/dci_api/dr/on-subscribe`

### Tabs

Disability Status form:

- **Disability Information**: Disability types and functional scores (JSON)
- **Raw Data**: Original JSON data received from DR system
- **Notes**: Additional notes about disability status
- **Error Details**: Error message if sync failed (visible only when error exists)

DR Sender form:

- **Public Key**: PEM-encoded public key for signature verification
- **Notes**: Additional notes about the DR registry

### Security

| Group               | Access                                                        |
| ------------------- | ------------------------------------------------------------- |
| `base.group_system` | Full CRUD on disability status and DR sender registry        |
| `base.group_user`   | Read/Write/Create disability status, read-only DR sender registry |

### Extension Points

- Override `DRService._extract_disability_data()` to customize parsing of DR response fields
- Override `DRService._extract_functional_scores()` to handle custom score formats
- Inherit `spp.dci.disability.status` to add domain-specific disability fields
- Extend callback router at `spp_dci_client_dr.routers.callback` to handle additional DR callback types

### Dependencies

`spp_dci_client`, `spp_dci_server`, `spp_registry`
