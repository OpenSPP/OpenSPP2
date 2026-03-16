OAuth 2.0 authentication framework for securing OpenSPP API communications using JWT tokens signed with RSA keys. Provides utility functions to generate and verify JWT signatures using the RS256 algorithm. Stores RSA key pairs as system parameters and exposes configuration UI for key management.

### Key Capabilities

- Generate JWT tokens signed with RSA private keys using `calculate_signature()`
- Verify and decode JWT tokens using RSA public keys via `verify_and_decode_signature()`
- Store and retrieve RSA key pairs (4096-bit recommended) through system parameters
- Configure OAuth keys through Settings UI with password-protected fields

### Key Models

| Model                 | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `res.config.settings` | Extended to add OAuth private and public key fields     |

### Utility Functions

| Function                        | Purpose                                              |
| ------------------------------- | ---------------------------------------------------- |
| `get_private_key()`             | Retrieves OAuth private key from system parameters   |
| `get_public_key()`              | Retrieves OAuth public key from system parameters    |
| `calculate_signature()`         | Encodes JWT with header and payload using RS256      |
| `verify_and_decode_signature()` | Decodes and verifies JWT token, returns payload      |
| `OpenSPPOAuthJWTException`      | Custom exception for OAuth JWT errors with logging   |

### Configuration

After installing:

1. Navigate to **Settings > General Settings**
2. Scroll to **SPP OAuth Settings** app block
3. Enter RSA private key (4096-bit recommended) in the **Private Key** field
4. Enter corresponding RSA public key in the **Public Key** field
5. Save settings

The keys are stored as system parameters:
- `spp_oauth.oauth_priv_key`
- `spp_oauth.oauth_pub_key`

### UI Location

- **Settings App Block**: SPP OAuth Settings (within Settings > General Settings)
- **Access**: Available to users with Settings access

### Security

| Group              | Access                                 |
| ------------------ | -------------------------------------- |
| `base.group_user`  | Read/Write (no create/delete)          |

Keys are displayed as password fields in the UI but stored as plain text in `ir.config_parameter`.

### Extension Points

- Import `calculate_signature()`, `verify_and_decode_signature()`, `get_private_key()`, and `get_public_key()` from `odoo.addons.spp_oauth.tools` to implement OAuth 2.0 authentication in custom API endpoints
- Catch `OpenSPPOAuthJWTException` for OAuth-specific error handling in API controllers

### Dependencies

`spp_security`, `base`

**External Python**: `pyjwt>=2.4.0`, `cryptography`
