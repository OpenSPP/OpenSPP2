Field-level encryption for PII data using AES-256-GCM with searchable blind indexes. Provides transparent encryption/decryption through a mixin, UI-based configuration of which fields to encrypt, and audit logging of PII field access.

### Key Capabilities

- Encrypt char/text fields transparently using AES-256-GCM authenticated encryption
- Search encrypted data via blind indexes without decryption (exact, partial, or phonetic matching)
- Configure field encryption through UI instead of code changes
- Audit all PII field access (reveal, export, decrypt, modify, delete) with IP and user agent tracking

### Key Models

| Model                                 | Description                                                      |
| ------------------------------------- | ---------------------------------------------------------------- |
| `spp.encrypted.field.mixin`           | Abstract mixin for models with encrypted PII fields              |
| `spp.field.encryption.config`         | UI-based configuration for enabling encryption on specific fields |
| `spp.pii.audit.log`                   | Audit log of PII field access events                             |

### Configuration

After installing:

1. Navigate to **Settings > Key Management > PII Encryption > Field Configuration**
2. Create a new configuration selecting the model and field to encrypt
3. Choose the blind index type: Exact (full normalized match), Partial (last 4 characters), or Phonetic (Soundex for names)
4. Enable encryption and blind index options

Bulk migration of existing plaintext data (scan, dry-run, backup, rollback) is provided separately and depends on the data classification module.

### UI Location

- **Configuration**: Settings > Key Management > PII Encryption > Field Configuration
- **Audit Log**: Settings > Key Management > PII Encryption > Audit Log

### Security

| Group                                        | Access                                                         |
| -------------------------------------------- | -------------------------------------------------------------- |
| `spp_pii_encryption.group_encryption_admin`  | Full CRUD on field configuration; Read on audit log            |
| `base.group_system`                          | Read/Create on audit logs                                      |
| `base.group_user`                            | Read field encryption configuration                            |

### Extension Points

- Inherit from `spp.encrypted.field.mixin` on any model with PII fields
- Implement `_get_encrypted_fields()` to specify which fields to encrypt (or configure via UI)
- Override `_get_encryption_key(field_name)` to customize key retrieval per field
- Override `_normalize_for_index(value, index_type)` to customize blind index normalization
- Use `search_by_blind_index(field_name, search_value)` to search encrypted fields
- Call `log_field_access(model, record_id, field, action, reason)` to audit PII access

### Dependencies

`base`, `spp_key_management`, `spp_registry`, `spp_security`
