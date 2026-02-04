# OpenSPP Key Management

Centralized cryptographic key management with pluggable providers for OpenSPP.

## Features

- **Envelope Encryption**: Data encryption keys (DEKs) protected by a master key (KEK)
- **Pluggable Providers**: Database provider included, extensible for HSM/KMS integration
- **Key Versioning**: Support for key rotation while maintaining decryption of old data
- **Asymmetric Keys**: RSA, EC (P-256, P-384, P-521), and Ed25519 key support
- **Purpose-based Keys**: Separate keys for different purposes (PII, credentials, etc.)

## Master Key Configuration

The master key encrypts all data keys stored in the database. It is resolved in this order:

### 1. Environment Variable (Recommended for Production)

```bash
export SPP_MASTER_KEY=$(python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
```

### 2. Configuration File

Add to `odoo.conf`:

```ini
spp_master_key = <base64-encoded-32-byte-key>
```

### 3. Auto-derived (Demo/Development Only)

If no explicit key is configured, a key is automatically derived from the database UUID. This provides a zero-config
experience for demos while logging a warning in non-demo mode.

**Security Note**: The derived key is deterministic per database, so encrypted data persists across restarts. However,
for production deployments, always use an explicit key via environment variable.

## Key Providers

### Database Provider

The default provider stores encrypted data keys in the database:

- Keys encrypted with AES-256-GCM using the master key
- Additional Authenticated Data (AAD) prevents key substitution attacks
- Supports multiple key versions for rotation

### Custom Providers

Implement the `spp.key.provider` abstract model to add support for:

- Hardware Security Modules (HSM)
- Cloud KMS (AWS KMS, Google Cloud KMS, Azure Key Vault)
- Other key storage backends

## Asymmetric Keys

The module supports asymmetric key pairs for signing and encryption:

```python
# Create an Ed25519 signing key
key = env["spp.asymmetric.key"].create({
    "name": "My Signing Key",
    "key_type": "ed25519",
    "storage_mode": "local",
})
key.generate_key_pair()

# Use the key
private_jwk = key.get_private_key_jwk()
public_jwk = json.loads(key.public_key_jwk)
```

### Supported Key Types

| Type      | Algorithms          | Use Case                   |
| --------- | ------------------- | -------------------------- |
| `rsa`     | RS256, RS384, RS512 | Legacy compatibility       |
| `ec`      | ES256, ES384, ES512 | Standard signatures        |
| `ed25519` | EdDSA               | Modern, compact signatures |

## Security Groups

- **Key Management / User**: View keys and basic operations
- **Key Management / Manager**: Create, rotate, and manage keys
- **Key Management / Admin**: Full access including provider configuration

## Dependencies

- `cryptography` Python package
- `spp_security` module

## Related Modules

- `spp_cbor_cose`: CBOR/COSE operations using keys from this module
- `spp_claim_169`: QR credential generation using asymmetric keys
