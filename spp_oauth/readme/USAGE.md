This module provides RSA-based JWT signing and verification utilities. It does not expose API endpoints — it is a utility library consumed by other modules that need RS256 JWT authentication. Testing focuses on the Settings UI and the JWT utility functions.

### Prerequisites

- `spp_oauth` module installed
- Admin or Settings-group access to the Odoo instance
- A signing keypair generated externally. RSA-2048 is the default
  recommendation — NIST-approved through 2030 and ~5× faster on sign/verify
  than RSA-4096. Use RSA-3072 or RSA-4096 only if your compliance policy
  requires it.

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
```

For new deployments, EC keys (P-256 → `ES256`) are even faster and produce
shorter tokens. Consuming modules that surface algorithm choice (e.g. the
`spp_api_v2_oauth` Trusted-Issuer model) accept `ES256/ES384/ES512` directly.

```bash
openssl ecparam -name prime256v1 -genkey -noout -out private.pem
openssl ec -in private.pem -pubout -out public.pem
```

### UI Tests

**Test 1: Settings UI Renders Correctly**

1. Log in as a user with **Settings** access
2. Navigate to **Settings > General Settings**
3. Scroll down to the **SPP OAuth Settings** app block

**Expected**:

- The app block is visible with the module icon and title "SPP OAuth Settings"
- Inside is a block titled **OAuth Settings (RSA or EC keys)**
- Two settings are displayed: **Private Key** and **Public Key**
- Both fields are masked (password input type) — values appear as dots

**Test 2: Save and Persist RSA Keys**

1. In the **SPP OAuth Settings** block, click the **Private Key** field and paste the contents of `private.pem`
2. Click the **Public Key** field and paste the contents of `public.pem`
3. Click **Save**
4. Navigate away from Settings, then return to **Settings > General Settings**
5. Scroll to **SPP OAuth Settings**

**Expected**:

- Both fields show masked content (dots), indicating values were saved
- The values persist after navigating away and returning

**Test 3: Verify Keys Stored in System Parameters**

1. Navigate to **Settings > Technical > Parameters > System Parameters**
2. Search for `spp_oauth`

**Expected**:

- Two parameters exist:
  - `spp_oauth.oauth_private_key` — contains the private key PEM text
  - `spp_oauth.oauth_public_key` — contains the public key PEM text

**Test 4: Non-Admin Users Cannot Access OAuth Settings**

1. Log in as a regular user (not in `base.group_system`)
2. Attempt to navigate to **Settings > General Settings**

**Expected**:

- The user cannot access the Settings page (menu is not visible or access is denied)
- OAuth keys are not exposed to non-admin users through the UI
- Only system administrators (`base.group_system`) can read or modify OAuth key settings

### Utility Function Tests

These tests require Odoo shell access (`odoo-bin shell`). They verify the JWT signing and verification functions that consuming modules rely on.

**Test 5: Missing Keys Produce Clear Error**

Precondition: RSA keys are **not** configured (clear both `spp_oauth.oauth_private_key` and `spp_oauth.oauth_public_key` in System Parameters).

```python
from odoo.addons.spp_oauth.tools import calculate_signature, OpenSPPOAuthJWTException

try:
    calculate_signature(env=env, header=None, payload={"test": "data"})
except OpenSPPOAuthJWTException as e:
    # Expected: OpenSPPOAuthJWTException raised
```

**Expected**:

- An `OpenSPPOAuthJWTException` is raised with message: "OAuth private key not configured in settings."

**Test 6: JWT Sign and Verify Round-Trip**

Precondition: RSA keys are configured (Test 2 completed).

```python
from odoo.addons.spp_oauth.tools import calculate_signature, verify_and_decode_signature

# Sign a payload
token = calculate_signature(
    env=env,
    header=None,
    payload={"user": "test", "action": "verify"},
)
# token is a JWT string (three base64 segments separated by dots)

# Verify and decode
decoded = verify_and_decode_signature(env=env, access_token=token)
# decoded contains {"user": "test", "action": "verify"}
```

**Expected**:

- `token` is a non-empty string in JWT format (three base64 segments separated by dots)
- `decoded` is a dict containing `{"user": "test", "action": "verify"}`

**Test 7: Tampered Token Is Rejected**

Precondition: RSA keys are configured (Test 2 completed).

```python
from odoo.addons.spp_oauth.tools import calculate_signature, verify_and_decode_signature, OpenSPPOAuthJWTException

token = calculate_signature(
    env=env,
    header=None,
    payload={"data": "original"},
)

# Tamper with the token signature
tampered = token[:-5] + "XXXXX"

try:
    verify_and_decode_signature(env=env, access_token=tampered)
except OpenSPPOAuthJWTException as e:
    # Expected: OpenSPPOAuthJWTException raised
```

**Expected**:

- An `OpenSPPOAuthJWTException` is raised

**Test 8: Token Signed With Wrong Key Is Rejected**

This test verifies that a token signed with a different private key cannot be verified with the configured public key.

Precondition: RSA keys are configured (Test 2 completed).

```python
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from odoo.addons.spp_oauth.tools import verify_and_decode_signature, OpenSPPOAuthJWTException

# Generate a different RSA key pair
other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
other_pem = other_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

# Sign a token with the wrong key
wrong_token = jwt.encode(
    payload={"data": "forged"},
    key=other_pem,
    algorithm="RS256",
)

try:
    verify_and_decode_signature(env=env, access_token=wrong_token)
except OpenSPPOAuthJWTException as e:
    # Expected: OpenSPPOAuthJWTException raised
```

**Expected**:

- An `OpenSPPOAuthJWTException` is raised (signature verification fails)
- The configured public key correctly rejects the foreign-signed token
