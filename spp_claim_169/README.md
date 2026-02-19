# OpenSPP Claim 169 QR Credentials

MOSIP Claim 169 QR code identity credential generation for OpenSPP.

## Features

- **Configurable Attribute Mapping**: Map OpenSPP fields to Claim 169 numbered
  attributes
- **CWT Generation**: Create signed CBOR Web Tokens using COSE Sign1
- **QR Code Generation**: Generate compressed, Base45-encoded QR codes
- **Registry Integration**: Seamlessly integrate with OpenSPP registry (res.partner)
- **Credential Management**: Track issued credentials, expiration, and revocation
- **Multi-issuer Support**: Configure multiple credential issuers

## Claim 169 Specification

MOSIP Claim 169 defines a standardized set of numbered attributes for identity
credentials:

### Demographics (1-23)

- **1**: ID
- **2**: Version
- **3**: Language
- **4**: Full Name
- **5**: First Name
- **6**: Middle Name
- **7**: Last Name
- **8**: Date of Birth (YYYYMMDD)
- **9**: Gender (1=Male, 2=Female, 3=Others)
- **10**: Address
- **11**: Email
- **12**: Phone
- **13**: Nationality (ISO 3166-1)
- **14**: Marital Status
- **15**: Guardian
- **16**: Photo (binary)
- **17**: Photo Format (1=JPEG, 2=JPEG2, 3=AVIF, 4=WEBP)

### Standard CWT Claims

- **iss (1)**: Issuer identifier
- **exp (4)**: Expiration timestamp
- **iat (6)**: Issued at timestamp

## Installation

1. Install dependencies:

   ```bash
   pip install qrcode Pillow
   ```

2. Install required modules:
   - `spp_registry`
   - `spp_cbor_cose`
   - `spp_key_management`

3. Install this module:
   ```bash
   odoo-bin -d <database> -i spp_claim_169
   ```

## Configuration

### 1. Set Up Signing Keys

Navigate to **Key Management** and create or import a private key for signing
credentials:

- Algorithm: ES256 (ECDSA with SHA-256)
- Format: PEM or JWK

### 2. Configure Issuer

Go to **Claim 169 > Configuration > Issuer Configurations**:

- Create a new issuer configuration
- Set issuer ID (e.g., DID or URI)
- Select signing key
- Configure default validity period

### 3. Customize Attribute Mappings

Go to **Claim 169 > Configuration > Attribute Mappings**:

- Review default mappings
- Add custom mappings as needed
- Configure transformations:
  - **Direct**: Use field value as-is
  - **Date YYYYMMDD**: Convert dates to integer format
  - **Gender Code**: Map to Claim 169 codes
  - **Address Combined**: Combine address fields
  - **CEL Expression**: Custom transformations (advanced)

## Usage

### Generate Credentials

1. Navigate to **Registry > Partners**
2. Select one or more partners
3. Click **Action > Generate QR Credentials**
4. Configure wizard options:
   - Select issuer
   - Set validity period
   - Choose generation mode:
     - **New Only**: Skip partners with existing credentials
     - **Replace Expired**: Replace only expired credentials
     - **Replace All**: Replace all existing credentials
5. Click **Generate**

### View Credentials

Go to **Claim 169 > Credentials** to view all generated credentials:

- View QR code images
- Download CWT data
- Check expiration status
- Revoke credentials

### Verify Credentials

Use the service API to verify credentials from QR data:

```python
service = env["spp.claim169.service"]
result = service.verify_credential(qr_data, public_key_id)

if result["valid"]:
    claims = result["claims"]
    # Process claims
else:
    error = result["error"]
    # Handle error
```

## Technical Architecture

### Credential Generation Flow

1. **Build Claims**: Extract values from partner using attribute mappings
2. **Create CWT**: Encode claims as CBOR and sign with COSE Sign1
3. **Compress**: Apply zlib compression to reduce size
4. **Encode**: Encode with Base45 for QR code compatibility
5. **Generate QR**: Create QR code image

### QR Code Format

```
[Base45] -> [zlib decompress] -> [COSE Sign1] -> [CBOR] -> [Claims Map]
```

### Models

- **spp.claim169.attribute.mapping**: Field mappings configuration
- **spp.claim169.issuer.config**: Issuer configurations
- **spp.claim169.credential**: Stored credentials with QR codes
- **spp.claim169.service**: Service for credential operations (AbstractModel)

### Security

Three-tier access control:

- **Claim 169 User**: View credentials, generate QR codes
- **Claim 169 Manager**: Manage configurations, revoke credentials
- **System Admin**: Full access

## API Reference

### Service Methods

#### `generate_cwt_for_partner(partner_id, issuer_config_id)`

Generate signed CWT for a partner.

**Returns**: `(cwt_bytes, qr_data)`

#### `encode_for_qr(cwt_bytes)`

Encode CWT bytes for QR code (compress + Base45).

**Returns**: Base45 encoded string

#### `decode_from_qr(qr_data)`

Decode QR data to CWT bytes (Base45 decode + decompress).

**Returns**: CWT bytes

#### `verify_credential(qr_data, public_key_id)`

Verify credential from QR data.

**Returns**: `{"valid": bool, "claims": dict, "error": str}`

## Dependencies

### Odoo Modules

- `base`
- `spp_registry`
- `spp_cbor_cose`
- `spp_key_management`

### Python Packages

- `qrcode`: QR code generation
- `Pillow`: Image processing

## Development

### Running Tests

```bash
./scripts/test_single_module.sh spp_claim_169
```

### Adding Custom Transformations

Extend `spp.claim169.attribute.mapping` to add new transformation types:

```python
class Claim169AttributeMapping(models.Model):
    _inherit = "spp.claim169.attribute.mapping"

    def _transform_value(self, value, partner):
        if self.transform_type == "custom":
            return self._transform_custom(value)
        return super()._transform_value(value, partner)

    def _transform_custom(self, value):
        # Custom transformation logic
        return transformed_value
```

## License

LGPL-3

## Author

OpenSPP.org

## Maintainers

- openspp-dev

## Links

- GitHub: https://github.com/OpenSPP/openspp-modules
- Documentation: https://docs.openspp.org
