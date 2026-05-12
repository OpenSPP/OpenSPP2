Provides encryption, decryption, digital signing, and signature verification for sensitive OpenSPP data. Implements JWE (JSON Web Encryption) for data protection and JWT (JSON Web Token) for signing. Supports JWKS (JSON Web Key Set) distribution for public key sharing and Linked Data Proof signatures for verifiable credentials. Integrates with `spp_key_management` for secure key storage.

### Key Capabilities

- Encrypt/decrypt data using JWE with RSA-OAEP and AES-256-GCM algorithms
- Sign and verify JWT tokens with RS256 algorithm
- Generate and distribute public keys in JWKS format for external verification
- Sign verifiable credentials with Linked Data Proof (JSON-LD signatures)
- Pluggable provider architecture via type selection field and dynamic method dispatch

### Key Models

| Model                     | Description                                                       |
| ------------------------- | ----------------------------------------------------------------- |
| `spp.encryption.provider` | Defines encryption provider with crypto operations and key linkage |

### Configuration

After installing:

1. Navigate to **Settings > Key Management > Encryption Providers**
2. A default provider is created automatically
3. Select the provider and configure the type field to `jwcrypto`
4. Click **Generate Key** to create encryption keys
5. Keys are stored encrypted in `spp.asymmetric.key` records via `spp_key_management`

### UI Location

- **Menu**: Settings > Key Management > Encryption Providers
- **Access**: Available to Crypto Viewer role and above

### Security

| Group                                 | Access                           |
| ------------------------------------- | -------------------------------- |
| `spp_encryption.group_crypto_viewer`  | Read only (audit purposes)       |
| `spp_encryption.group_crypto_officer` | Read/Write/Create (no delete)    |
| `spp_encryption.group_crypto_manager` | Full CRUD including key deletion |
| `spp_encryption.group_crypto_admin`   | Full CRUD (legacy, maps to manager) |

### Extension Points

- Add new provider types by extending the `type` selection field on `spp.encryption.provider`
- Implement `encrypt_data_{type}`, `decrypt_data_{type}`, `jwt_sign_{type}`, `jwt_verify_{type}` methods for custom providers
- Override `sign_credential_ld_proof_{type}` for custom credential signing logic
- Override `get_jwks_{type}` for custom public key distribution formats

### Dependencies

`spp_security`, `spp_key_management`

External: `jwcrypto>=1.5.6`, `pyld` (for JSON-LD normalization)
