Enables OpenSPP deployed as a Management Information System to query external Social Registries via the DCI protocol. Caches beneficiary demographic data, household composition, and program enrollments from remote SR systems. Verifies cryptographic signatures on SR callbacks and processes real-time notifications for enrollment changes.

### Key Capabilities

- Search external Social Registries for person and household data by identifier
- Cache demographic fields, household relationships, and program enrollment status from SR responses
- Receive async callbacks for search results, subscription confirmations, and event notifications
- Verify signatures on SR callbacks using Ed25519 (other algorithms reserved for future use)
- Subscribe to enrollment, disenrollment, and update events from trusted SR systems
- Query enrollment status and check beneficiary eligibility against SR data
- Refresh cached SR data on demand or retry failed syncs

### Key Models

| Model               | Description                                                    |
| ------------------- | -------------------------------------------------------------- |
| `spp.dci.sr.sender` | Registry of trusted SR systems with sender IDs and public keys |
| `spp.dci.sr.record` | Cached person record from external SR with demographics        |

### Configuration

After installing:

1. Navigate to **DCI > Configuration > SR Senders**
2. Create an SR sender with sender ID, base URL, signature algorithm (Ed25519), and PEM-encoded public key
3. Use **Test Connection** button to verify connectivity
4. Ensure the `dci_api` FastAPI endpoint is configured in `spp_dci_client`

### UI Location

- **Menu**: DCI > Configuration > SR Senders
- **Menu**: DCI > Activity Logs > SR Records
- **Form tabs** (SR Sender): Public Key, Notes
- **Form tabs** (SR Record): SR Data, Program Enrollment, Raw Data, Error Details
- **Actions**: Refresh from SR, Retry Sync, Mark as Stale (buttons on SR record form)

### FastAPI Endpoints

Extends the `dci_api` FastAPI app with callback routes:

- `POST /sr/on-search` - Receive async search responses from SR
- `POST /sr/on-subscribe` - Receive subscription confirmations
- `POST /sr/on-notify` - Receive enrollment/disenrollment/update notifications

All endpoints verify signatures using the `verify_sr_signature` middleware.

### Security

| Group                                | Access                                          |
| ------------------------------------ | ----------------------------------------------- |
| `spp_registry.group_registry_viewer` | Read SR senders and records                     |
| `spp_registry.group_registry_officer`| Read SR senders, read/write SR records          |
| `spp_registry.group_registry_manager`| Full CRUD on SR senders and records             |

### Extension Points

- Inherit `spp.dci.sr.sender` to add custom SR metadata or connection testing logic
- Inherit `spp.dci.sr.record` to extend cached data fields
- Use `SRService(env, data_source_code)` class to query SRs from custom Python code
- Override `_update_from_sr_response(data)` on `spp.dci.sr.record` to customize data extraction from SR responses

### Dependencies

`spp_dci_client`, `spp_registry`
