# Quick Start Guide - spp_claim_169

Get started with MOSIP Claim 169 QR credential generation in 5 minutes.

## Installation

### 1. Install Python Dependencies

```bash
pip install qrcode Pillow
```

### 2. Install Odoo Module

```bash
odoo-bin -d <database> -i spp_claim_169
```

Or via UI: Apps > Update Apps List > Search "Claim 169" > Install

## Basic Setup

### Step 1: Create/Import Signing Key

1. Navigate to **Key Management**
2. Create or import a private key:
   - **Name**: "Claim 169 Signing Key"
   - **Algorithm**: ES256 (ECDSA with SHA-256)
   - **Key Type**: Private
   - **Format**: PEM or JWK

### Step 2: Configure Issuer

1. Go to **Claim 169 > Configuration > Issuer Configurations**
2. Click **Create**
3. Fill in:
   - **Name**: "National ID Program"
   - **Issuer ID**: "did:openspp:national-id" (or your DID/URI)
   - **Signing Key**: Select the key from Step 1
   - **Default Validity**: 365 days
   - **Default Issuer**: ✓ (check this)
4. Click **Save**

### Step 3: Review Attribute Mappings

1. Go to **Claim 169 > Configuration > Attribute Mappings**
2. Review default mappings (active by default):
   - Claim 1: ID
   - Claim 4: Full Name
   - Claim 8: Date of Birth
   - Claim 9: Gender
   - Claim 10: Address
   - Claim 11: Email
   - Claim 12: Phone
3. Customize as needed (activate/deactivate, add custom mappings)

## Generate Your First Credential

### Via UI Wizard (Recommended)

1. Navigate to **Registry > Partners**
2. Select one or more registrants
3. Click **Action > Generate QR Credentials**
4. In the wizard:
   - **Issuer**: Auto-selected (default issuer)
   - **Validity**: 365 days (from issuer default)
   - **Mode**: "New Only" (skip if exists)
5. Click **Generate**
6. Review results
7. Click **View Credentials** to see generated QR codes

### Via Code

```python
# Get or create partner
partner = env["res.partner"].search([("spp_id", "=", "REG-001")], limit=1)

# Get default issuer
issuer = env["spp.claim169.issuer.config"].search([("is_default", "=", True)], limit=1)

# Create credential
credential = env["spp.claim169.credential"].create({
    "partner_id": partner.id,
    "issuer_config_id": issuer.id,
    "issued_at": fields.Datetime.now(),
    "expires_at": fields.Datetime.now() + timedelta(days=365),
})

# Generate CWT and QR
credential.generate_credential()

# Access data
print(f"Credential ID: {credential.name}")
print(f"QR Data (Base45): {credential.qr_data}")
print(f"Hash: {credential.credential_hash}")

# QR image is in credential.qr_image (binary PNG)
```

## View Credentials

1. Go to **Claim 169 > Credentials**
2. View options:
   - **List View**: Table of all credentials
   - **Kanban View**: Visual cards with QR codes
   - **Form View**: Detailed credential information
3. Filters:
   - Active, Expired, Revoked
   - Issued This Month
   - Group by Partner, Issuer, Status

## Verify a Credential

```python
service = env["spp.claim169.service"]

# Get public key for verification
public_key = issuer.signing_key_id.get_public_key()  # Implement as needed

# Verify from QR data
result = service.verify_credential(qr_data, public_key.id)

if result["valid"]:
    claims = result["claims"]
    print(f"Valid credential!")
    print(f"Issuer: {claims.get(1)}")
    print(f"Full Name: {claims.get(4)}")
    print(f"DOB: {claims.get(8)}")
    print(f"Gender: {claims.get(9)}")
else:
    print(f"Invalid: {result['error']}")
```

## Common Operations

### Revoke a Credential

1. Open credential form
2. Click **Revoke** button
3. Confirm action
4. Status changes to "Revoked"

Or via code:

```python
credential.action_revoke()
```

### Regenerate a Credential

1. Open credential form
2. Click **Regenerate** button
3. New CWT and QR generated with updated expiration

Or via code:

```python
credential.action_regenerate()
```

### Add Custom Attribute Mapping

1. Go to **Claim 169 > Configuration > Attribute Mappings**
2. Click **Create**
3. Fill in:
   - **Name**: "Marital Status"
   - **Claim Number**: 14
   - **Claim Name**: "marital_status"
   - **Source Field**: "marital"
   - **Transform Type**: "Direct"
   - **Active**: ✓
   - **Sequence**: 100
4. Click **Save**
5. New credentials will include this field

## Understanding QR Code Data

The QR code contains:

1. **Base45 Encoded String** (what you see in `qr_data`)
2. Which decodes to **Compressed CBOR** (zlib)
3. Which decompresses to **COSE Sign1 Structure**
4. Which contains **Signed CWT**
5. Which contains **Claims Map** with Claim 169 attributes

Example flow:

```
QR Code → Base45 String → Zlib Compressed → COSE Sign1 → CWT → Claims
```

## Claim 169 Attribute Reference

| Number | Name          | Type    | Example                    |
| ------ | ------------- | ------- | -------------------------- |
| 1      | ID            | String  | "REG-12345"                |
| 4      | Full Name     | String  | "John Doe"                 |
| 8      | Date of Birth | Integer | 19900115 (YYYYMMDD)        |
| 9      | Gender        | Integer | 1=Male, 2=Female, 3=Others |
| 10     | Address       | String  | "123 Main St, City"        |
| 11     | Email         | String  | "john@example.com"         |
| 12     | Phone         | String  | "+1234567890"              |

Standard CWT claims:

- **iss (1)**: Issuer DID/URI
- **iat (6)**: Issued timestamp (Unix epoch)
- **exp (4)**: Expiration timestamp (Unix epoch)

## Security Notes

1. **Private Keys**: Keep signing keys secure
2. **Access Control**:
   - Users: View and generate credentials
   - Managers: Configure and revoke
3. **Key Rotation**: Update issuer signing key when rotating
4. **Revocation**: No automatic revocation list - check status in system

## Troubleshooting

### "No signing key found"

- Ensure you created a private key in Key Management
- Check issuer configuration has signing key selected

### "Failed to generate CWT"

- Verify spp_cbor_cose module is installed
- Check signing key is valid and accessible

### "Invalid attribute mapping"

- Ensure source field exists on res.partner
- Check transform type matches field type (e.g., date_yyyymmdd for date fields)

### QR code not generating

- Verify qrcode and Pillow are installed: `pip list | grep -E "(qrcode|Pillow)"`
- Check credential has qr_data field populated

## Next Steps

1. **Customize Mappings**: Add fields specific to your use case
2. **Multiple Issuers**: Create different issuers for different programs
3. **Integrate Verification**: Build verification endpoints for QR scanning
4. **Automate Generation**: Set up scheduled jobs for credential renewal
5. **Extend Transformations**: Add custom transform types for complex logic

## Support

- Documentation: https://docs.openspp.org
- GitHub: https://github.com/OpenSPP/openspp-modules
- Issues: https://github.com/OpenSPP/openspp-modules/issues

## Module Info

- **Version**: 19.0.1.0.0
- **License**: LGPL-3
- **Author**: OpenSPP.org
- **Module**: spp_claim_169
