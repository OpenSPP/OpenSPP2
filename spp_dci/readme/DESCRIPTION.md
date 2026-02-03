Core DCI (Digital Convergence Initiative) infrastructure for OpenSPP. Implements SPDCI messaging protocol with HTTP signature authentication, Pydantic schemas for message validation, and cryptographic key management. Provides foundational components for building DCI-compliant registry integrations.

### Key Capabilities

- Manage signing keys with Ed25519 and RSA-256 algorithms, state-based lifecycle (draft → active → revoked)
- Generate HTTP signatures following draft-cavage specification for outbound message authentication
- Verify incoming HTTP signatures using JWKS public key discovery
- Validate DCI message structure using Pydantic schemas (envelope, header, payload)
- Export standard identifier types (UIN, BRN, MRN, DRN) with DCI namespace URIs
- Build and sign DCI response envelopes with centralized helper functions

### Key Models

| Model                  | Description                                                |
| ---------------------- | ---------------------------------------------------------- |
| `spp.dci.signing.key`  | Cryptographic signing key with lifecycle state management  |

### Pydantic Schemas

Exported in `spp_dci.schemas` for import by DCI server/client modules:

- **Envelope**: `DCIEnvelope`, `DCIMessageHeader`, `DCICallbackHeader` - Three-part message structure
- **Common**: `Identifier`, `Name`, `Address`, `GeoLocation`, `Place`, `AdditionalAttribute`, `Period` - Shared data types
- **Person/Group**: `Person`, `RelatedPerson`, `DisabilityInfo`, `Group`, `Member` - Registry entities
- **Search**: `SearchRequest`, `SearchResponse`, `SearchCriteria`, `Pagination`, `Expression` - Search operations
- **Subscription**: `SubscribeRequest`, `SubscribeResponse`, `UnsubscribeRequest`, `TxnStatusRequest` - Event subscriptions
- **Receipt**: `ReceiptRequest`, `ReceiptResponse`, `BeneficiaryRef`, `ReceiptInformation` - Delivery confirmations

### Configuration

After installing:

1. Navigate to **Settings > Technical > Parameters > System Parameters**
2. Set `dci.sender_id` to your organization's DCI identifier (default: `openspp`)
3. Create signing keys at **Settings > Technical > Database Structure > DCI Signing Keys**
4. Generate keypair, then activate the key for use in signatures

### UI Location

No standalone menu. Access signing keys via **Settings > Technical > Database Structure > DCI Signing Keys**.

### Security

| Group                  | Access                        |
| ---------------------- | ----------------------------- |
| `base.group_system`    | Full CRUD, view private keys  |
| `base.group_user`      | Read signing keys (no delete) |

### Extension Points

- Inherit `spp.dci.signing.key` to add key rotation policies or HSM integration
- Use `DCISigner(private_key, sender_id, key_id, algorithm)` to sign outbound messages
- Use `DCIVerifier(public_key, algorithm)` to verify incoming signatures
- Import schemas from `spp_dci.schemas` for message validation in custom endpoints
- Override `get_sender_id(env)` in `response_helpers` to customize sender identification
- Use `build_signed_envelope()` helper to construct DCI responses with proper headers and signatures

### Dependencies

`base`, `spp_registry`
