Receives vital event notifications from Civil Registration and Vital Statistics (CRVS) systems via DCI protocol webhooks and updates registry partner records accordingly. Verifies incoming callback signatures using stored public keys of trusted CRVS registries.

### Key Capabilities

- Receive and log vital events: birth, death, marriage, divorce from CRVS systems
- Match events to registry partners using identifiers (BRN, DRN, MRN, UIN)
- Update partner records: birthdate, death status, civil status, registry identifiers
- Process events with state tracking: received → processing → processed/error
- Verify DCI callback signatures using JWKS public keys from trusted CRVS registries
- Fetch and store CRVS public keys automatically from JWKS endpoints
- Retry failed event processing through UI actions

### Key Models

| Model                   | Description                                                   |
| ----------------------- | ------------------------------------------------------------- |
| `spp.dci.crvs.event`    | Vital event log with identifier, type, date, processing state |
| `spp.dci.crvs.sender`   | Trusted CRVS registry with sender ID and public key           |

### Configuration

After installing:

1. Navigate to **Settings > Technical > DCI > Configuration > CRVS Sender Registry**
2. Create entries for each trusted CRVS registry with sender ID and JWKS URL
3. Click **Fetch Public Key** to retrieve and store the public key
4. Configure webhook endpoints on CRVS systems to send callbacks to OpenSPP DCI API

### UI Location

- **Events**: Settings > Technical > DCI > Activity Logs > CRVS Events
- **Sender Registry**: Settings > Technical > DCI > Configuration > CRVS Sender Registry
- **Event form tabs**: "Raw Data", "Notes"
- **Sender form tabs**: "Public Key", "Notes"

### Security

| Group               | CRVS Event Access       | CRVS Sender Access |
| ------------------- | ----------------------- | ------------------ |
| `base.group_system` | Full CRUD               | Full CRUD          |
| `base.group_user`   | Read/Write/Create only  | Read-only          |

### Extension Points

- Override `_process_birth_event()`, `_process_death_event()`, `_process_marriage_event()`, `_process_divorce_event()` to customize partner record updates based on event type
- Override `_find_person_by_identifier()` to implement custom matching logic
- Inherit `spp.dci.crvs.event` to add fields for domain-specific event metadata
- Use `CRVSService` class for programmatic access to verify_birth(), check_death(), subscribe_events()

### Dependencies

`spp_dci_client`, `spp_registry`
