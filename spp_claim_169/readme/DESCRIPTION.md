Generates MOSIP Claim 169 QR code identity credentials for registrants. Uses cryptographic signing to create verifiable credentials that can be scanned and validated offline. Integrates with OpenSPP key management for secure credential issuance and audit logging for credential lifecycle tracking.

### Key Capabilities

- Generate signed QR credentials using MOSIP Claim 169 standard with Ed25519 or EC keys
- Configure mappings from partner fields to numbered claim attributes (1-99)
- Track credential lifecycle with automatic expiration and manual revocation
- Verify credential authenticity using public key verification
- Transform data with multiple formats: direct copy, date formatting, gender codes, address combination, and CEL expressions
- Batch generate credentials for multiple registrants with configurable replacement modes
- Audit credential generation, revocation, and download events

### Key Models

| Model                              | Description                                                |
| ---------------------------------- | ---------------------------------------------------------- |
| `spp.claim169.credential`          | Stores issued credentials with QR codes and validity dates |
| `spp.claim169.issuer.config`       | Defines issuer identity and signing keys                   |
| `spp.claim169.attribute.mapping`   | Maps partner fields to claim attribute numbers             |
| `spp.claim169.service`             | Service for credential generation and verification         |
| `spp.claim169.generate.qr.wizard`  | Wizard for batch credential generation                     |
| `spp.claim169.verify.qr.wizard`    | Wizard for credential verification                         |

### Configuration

After installing:

1. Navigate to **Registry > Configuration > QR Credentials > Issuer Configurations**
2. Create an issuer with a DID identifier and select a signing key from `spp_key_management`
3. Set default validity period in days
4. Navigate to **Registry > Configuration > QR Credentials > Attribute Mappings**
5. Map partner fields (e.g., `name`, `birthdate`, `gender`) to claim numbers (1-99)
6. Choose transform type for each mapping (direct, date formatting, gender codes, CEL)

### UI Location

- **Configuration**: Registry > Configuration > QR Credentials
  - Issuer Configurations
  - Attribute Mappings
- **Credentials**: Accessed from registrant profile under "QR Credentials" section on Identity tab
- **Generate**: Button on partner form opens generation wizard
- **Verify**: Use verification wizard to validate credentials

### Security

| Group                                    | Credentials        | Configuration      | Wizards   |
| ---------------------------------------- | ------------------ | ------------------ | --------- |
| `spp_claim_169.group_claim169_user`      | Read, Create       | Read only          | Full CRUD |
| `spp_claim_169.group_claim169_manager`   | Full CRUD          | Full CRUD          | Full CRUD |

### Extension Points

- Override `spp.claim169.attribute.mapping._transform_value()` to add custom transformation types
- Inherit `spp.claim169.service._build_claim169_input()` to customize claim structure
- Extend `spp.claim169.credential` to add domain-specific metadata fields

### Dependencies

`base`, `mail`, `spp_security`, `spp_registry`, `spp_key_management`, `spp_audit`, `spp_cel_domain`
