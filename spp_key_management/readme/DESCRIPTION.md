Centralized cryptographic key management with pluggable provider architecture. Supports symmetric encryption (AES-256-GCM) and asymmetric signing (RSA, EC, Ed25519) with keys stored in database, configuration files, or enterprise KMS backends (HashiCorp Vault, AWS KMS, GCP KMS, Azure Key Vault). Provides envelope encryption, key rotation, blind index computation, and audit logging of key operations.

### Key Capabilities

- Symmetric encryption/decryption using AES-256-GCM with envelope encryption pattern
- Asymmetric key management for JWT signing and credential issuance (RSA, EC, Ed25519)
- Blind index computation using HMAC-SHA256 for searchable encrypted data
- Key rotation with versioning (old versions remain available for decryption)
- Pluggable provider system: switch between local database storage and enterprise KMS
- HSM/KMS signing operations where private keys never leave secure hardware
- Audit logging of all key access operations (without logging sensitive key material)

### Key Models

| Model                             | Description                                              |
| --------------------------------- | -------------------------------------------------------- |
| `spp.key.manager`                 | Main service interface for all key operations            |
| `spp.encryption.key`              | Encrypted key storage with versioning support            |
| `spp.key.provider`                | Abstract base class for key provider implementations     |
| `spp.key.provider.registry`       | Registry configuring which provider serves which purpose |
| `spp.key.purpose`                 | Purpose definitions (PII, financial, credentials, etc)   |
| `spp.asymmetric.key`              | RSA/EC/Ed25519 key pairs for signing operations          |
| `spp.key.provider.config`         | Configuration file provider (development)                |
| `spp.key.provider.database`       | Database provider using envelope encryption              |
| `spp.key.provider.vault`          | HashiCorp Vault integration                              |
| `spp.key.provider.aws.kms`        | AWS Key Management Service integration                   |
| `spp.key.provider.gcp.kms`        | Google Cloud KMS integration                             |
| `spp.key.provider.azure.keyvault` | Azure Key Vault integration                              |

### Configuration

After installing:

1. Navigate to **Settings > Administration > Key Management > Key Providers**
2. The default Database Provider is pre-configured
3. To use enterprise KMS: create a provider record, select type (Vault/AWS/GCP/Azure), configure connection details
4. Navigate to **Key Purposes** to view predefined purposes (pii, financial, credentials, api, backup)
5. Assign purposes to specific providers, or leave empty to use the default provider
6. Use **Test Connection** button on provider records to verify KMS connectivity

### UI Location

- **Menu**: Settings > Administration > Key Management
- **Submenus**:
  - Key Providers (configure which KMS backend to use)
  - Encryption Keys (view stored keys and versions)
  - Asymmetric Keys (manage signing keys for credentials)
  - Key Purposes (define key segregation policies)

### Security

| Group                                           | Access                                              |
| ----------------------------------------------- | --------------------------------------------------- |
| `spp_key_management.group_key_admin`            | Read/Write/Create on all models, key rotation       |
| `spp_key_management.group_key_operator_officer` | Read encryption keys for use in operations          |
| `base.group_system`                             | Full access to all key management features          |

Encryption keys and asymmetric keys cannot be deleted (enforced by Python `unlink()` override). All key access operations are logged with user, operation type, and purpose/key_id (without logging actual key material).

### Extension Points

- Inherit `spp.key.provider` and implement `get_data_key()` and `get_index_salt()` to add custom KMS backends
- Override `spp.key.manager.encrypt()` or `decrypt()` to customize encryption behavior
- Call `key_manager.get_key(purpose, key_id)` from other modules to retrieve keys for encryption
- Call `key_manager.compute_blind_index(value, purpose, salt_id)` to create searchable indexes for encrypted fields
- Use `spp.asymmetric.key.sign(data)` for HSM-backed signing without exposing private keys

### Dependencies

`base`, `spp_security`

External Python dependencies: `cryptography`
