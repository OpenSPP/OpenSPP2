# spp_claim_169 Module Summary

Complete Odoo 19 module for MOSIP Claim 169 QR code credential generation.

## Module Structure

```
spp_claim_169/
├── __init__.py
├── __manifest__.py
├── README.md
├── MODULE_SUMMARY.md
├── data/
│   └── default_mappings.xml          # Default attribute mappings (Claims 1,4,8,9,10,11,12)
├── models/
│   ├── __init__.py
│   ├── attribute_mapping.py          # spp.claim169.attribute.mapping
│   ├── issuer_config.py              # spp.claim169.issuer.config
│   ├── credential.py                 # spp.claim169.credential
│   └── claim169_service.py           # spp.claim169.service (AbstractModel)
├── wizards/
│   ├── __init__.py
│   ├── generate_qr_wizard.py         # spp.claim169.generate.qr.wizard
│   └── generate_qr_views.xml
├── views/
│   ├── attribute_mapping_views.xml
│   ├── issuer_config_views.xml
│   ├── credential_views.xml
│   └── menu_views.xml
├── security/
│   ├── security_groups.xml           # Two security groups with record rules
│   └── ir.model.access.csv           # Three-tier access control
├── tests/
│   ├── __init__.py
│   └── test_claim169.py              # Comprehensive test suite
└── static/
    └── description/
        ├── icon.png.txt              # Placeholder for module icon
        └── index.html                # Module description page
```

## Models

### 1. spp.claim169.attribute.mapping

Configurable mapping from OpenSPP fields to Claim 169 numbered attributes.

**Key Features:**

- Claim numbers 1-99
- Multiple transform types: direct, date_yyyymmdd, gender_code, address_combined, cel
- Active/inactive toggle
- Sequence ordering
- Validation: unique active claim numbers

**Methods:**

- `get_value(partner)` - Extract and transform value from partner

### 2. spp.claim169.issuer.config

Issuer configuration for credential generation.

**Key Features:**

- Issuer ID (DID or identifier)
- Signing key integration
- Default validity period
- Default issuer flag
- Multi-company support

**Methods:**

- `action_view_credentials()` - View credentials issued by this issuer

### 3. spp.claim169.credential

Stored credentials with QR codes.

**Key Features:**

- Partner reference
- CWT bytes storage
- QR data (Base45 encoded)
- QR image generation
- Status tracking (active/expired/revoked)
- Credential hash (SHA256)
- Revocation tracking
- Chatter integration

**Methods:**

- `generate_credential()` - Generate CWT and QR from partner data
- `action_revoke()` - Revoke credential
- `action_regenerate()` - Regenerate credential
- `_generate_qr_image()` - Create QR code image

### 4. spp.claim169.service (AbstractModel)

Main service for credential operations.

**Methods:**

- `generate_cwt_for_partner(partner_id, issuer_config_id)` - Generate signed CWT
- `encode_for_qr(cwt_bytes)` - Compress and Base45 encode
- `decode_from_qr(qr_data)` - Decode and decompress
- `verify_credential(qr_data, public_key_id)` - Verify credential
- `_encode_base45(data)` - Base45 encoding implementation
- `_decode_base45(data)` - Base45 decoding implementation

## Wizards

### spp.claim169.generate.qr.wizard

Batch credential generation wizard.

**Features:**

- Multi-partner selection
- Issuer configuration
- Custom validity period
- Generation modes: new_only, replace_expired, replace_all
- HTML result summary
- Link to generated credentials

## Security

### Groups

- **group_claim169_user**: View credentials, generate QR codes
- **group_claim169_manager**: Manage configurations, revoke credentials

### Record Rules

- Company-based access control
- User/Manager access levels for all models

### Access Rights

- Complete ir.model.access.csv with user/manager tiers

## Views

### Attribute Mappings

- Tree: Drag-drop reordering with handle widget
- Form: Full configuration with CEL expression editor
- Search: Filter by active status, group by transform type

### Issuer Configurations

- Tree: Key information with toggle widgets
- Form: Full configuration with credential count stat button
- Search: Filter by active/default status

### Credentials

- Tree: Status badges with color coding
- Kanban: Visual QR code display
- Form: Complete details with QR image, CWT data, revocation info
- Search: Multiple filters and grouping options

### Menu Structure

- Root: "Claim 169" application menu
- Credentials submenu
- Configuration submenu (manager only)
  - Issuer Configurations
  - Attribute Mappings

## Data

### Default Mappings

Pre-configured mappings for common attributes:

- Claim 1: ID (spp_id)
- Claim 4: Full Name (name)
- Claim 8: Date of Birth (birthdate → YYYYMMDD)
- Claim 9: Gender (gender → code 1/2/3)
- Claim 10: Address (combined address fields)
- Claim 11: Email
- Claim 12: Phone

### Sequences

- IR sequence for credential IDs: C169-XXXXXX

## Tests

Comprehensive test suite covering:

- Attribute mapping extraction
- Date/gender/address transformations
- Validation constraints
- Base45 encoding/decoding
- Issuer configuration
- Credential lifecycle
- Wizard functionality
- Hash computation
- QR compression
- Expiration handling

**Test Count:** 20+ test methods

## Dependencies

### Odoo Modules

- base
- mail (for chatter)
- spp_registry
- spp_cbor_cose
- spp_key_management

### Python Packages

- qrcode
- Pillow

## Technical Highlights

### Base45 Implementation

Complete Base45 encoding/decoding implementation per ISO/IEC 18004 Annex G:

- Charset: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%\*+-./:"
- Handles 1-byte and 2-byte encoding
- Proper error handling

### QR Code Pipeline

```
Partner Data → Attribute Mappings → Claims Map → CBOR Encoding →
COSE Sign1 → Zlib Compression → Base45 Encoding → QR Code Image
```

### Transformation System

Flexible transformation framework:

- Direct pass-through
- Date to YYYYMMDD integer
- Gender to numeric codes
- Address field combination
- CEL expression support (extensible)

### Status Management

Automatic status computation:

- Active: Not expired, not revoked
- Expired: Past expiration date
- Revoked: Manually revoked with tracking

## OpenSPP Standards Compliance

- ✅ Naming: `spp_*` module, `spp.*` models
- ✅ Boolean fields: `is_active`, `is_default`
- ✅ Many2one: `*_id`, Many2many: `*_ids`
- ✅ Logging: `_logger` only, no print()
- ✅ Error handling: Specific exceptions, no bare except
- ✅ Security: Three-tier access control
- ✅ Odoo 19: Command API, @api.constrains patterns
- ✅ Tests: Comprehensive coverage
- ✅ Documentation: Complete README and docstrings

## Usage Examples

### Generate Credential Programmatically

```python
# Create credential
credential = env["spp.claim169.credential"].create({
    "partner_id": partner.id,
    "issuer_config_id": issuer.id,
    "issued_at": fields.Datetime.now(),
    "expires_at": fields.Datetime.now() + timedelta(days=365),
})

# Generate CWT and QR
credential.generate_credential()

# Access QR data
qr_data = credential.qr_data
qr_image = credential.qr_image
```

### Verify Credential

```python
service = env["spp.claim169.service"]
result = service.verify_credential(qr_data, public_key_id)

if result["valid"]:
    claims = result["claims"]
    issuer = claims.get(1)  # iss claim
    expiration = claims.get(4)  # exp claim
    full_name = claims.get(4)  # Full name
    dob = claims.get(8)  # Date of birth
```

### Custom Attribute Mapping

```python
mapping = env["spp.claim169.attribute.mapping"].create({
    "name": "Custom Field",
    "claim_number": 20,
    "claim_name": "custom_field",
    "source_field": "x_custom_field",
    "transform_type": "direct",
    "is_active": True,
})
```

## Installation & Configuration

1. Install module dependencies
2. Install module: `odoo-bin -d <db> -i spp_claim_169`
3. Configure signing keys in Key Management
4. Create issuer configuration
5. Review/customize attribute mappings
6. Generate credentials via wizard or API

## Future Enhancements

Potential extensions:

- Photo field support (Claim 16-17)
- Biometric data integration
- CEL expression evaluator
- Credential templates
- Batch verification API
- QR code customization
- Expiration notifications
- Automatic renewal

## License

LGPL-3

## Author

OpenSPP.org
