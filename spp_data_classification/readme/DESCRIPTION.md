Data sensitivity classification registry for OpenSPP. Defines classification levels, maps model fields to those levels with PII categorization, and provides regex/CEL auto-detection patterns. This is the foundation other modules consume to decide what to encrypt, mask, or audit.

### Key Capabilities

- Define sensitivity levels (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED) with encryption, masking, audit, consent, and retention policy flags
- Map model fields to classification levels with PII categorization (direct identifiers, quasi-identifiers, biometric, health, financial, etc.)
- Flag classified fields as PII (`is_pii`, derived from the assigned PII category) so consumers can query them
- Auto-classify fields using regex (or CEL) patterns that match field names and metadata, via a manually-invoked scan

### Key Models

| Model                              | Description                                                          |
| ---------------------------------- | -------------------------------------------------------------------- |
| `spp.data.classification.level`    | Sensitivity levels with encryption, masking, and retention policies  |
| `spp.field.classification`         | Maps specific model fields to classification levels and PII category |
| `spp.classification.pattern`       | Auto-detection patterns using regex or CEL expressions               |

### Configuration

After installing:

1. Navigate to **Settings > Data Classification > Classification Levels** to review pre-loaded sensitivity levels (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)
2. Review **Detection Patterns** to customize auto-classification rules for your organization
3. Map fields under **Field Classifications**

### UI Location

- **Menu**: Settings > Data Classification
- **Classification Levels**: Settings > Data Classification > Classification Levels
- **Field Classifications**: Settings > Data Classification > Field Classifications
- **Detection Patterns**: Settings > Data Classification > Detection Patterns

### Security

| Group                                                  | Access                                                   |
| ------------------------------------------------------ | -------------------------------------------------------- |
| `spp_data_classification.group_classification_admin`   | Full CRUD on levels, patterns, and field classifications; implies Manager |
| `spp_data_classification.group_classification_manager` | Read/Write/Create field classifications (no delete); read-only on levels and patterns |
| `base.group_system`                                    | Full CRUD via explicit ACLs. The admin group deliberately does **not** imply system administration (and vice versa) |
| `base.group_user`                                      | Read-only access to classifications                      |

The `pii_full_access` and `pii_confidential_access` groups are defined for downstream masking/access-control consumers.

### Extension Points

- Query `spp.field.classification` to discover classified/PII fields per model (e.g. `get_fields_requiring_encryption()`)
- Override `spp.classification.pattern.matches_field()` to implement custom detection logic
- Add custom PII categories by extending the `pii_category` selection field

### Deferred subsystems

PII-aware enforcement (automatic read-time masking + the `pii=`/`classification=` field attributes), GDPR DSAR handling, data-retention scheduling, and consent integration are part of this module's design but are delivered in a separate governance change. This module ships the classification registry only.

### Dependencies

`base`, `spp_security`
