Bridge module that enables RS256 (asymmetric RSA) JWT authentication for the OpenSPP API V2. Automatically installed when both `spp_api_v2` and `spp_oauth` are present.

### What It Does

- Adds RS256 token verification alongside existing HS256 support — both algorithms are accepted simultaneously
- Provides a dedicated `/oauth/token/rs256` endpoint for generating RS256-signed JWT tokens
- Routes incoming tokens to the correct verification path based on the JWT header's `alg` field
- Enforces the same security controls as HS256: audience, issuer, and expiration validation

### When To Use RS256

RS256 uses asymmetric RSA keys (public/private pair) instead of a shared secret:

- **Distributed deployments**: External systems can verify tokens using only the public key, without access to the signing secret
- **Zero-trust architectures**: The private key never leaves the token issuer
- **Regulatory compliance**: Some security standards require asymmetric signing

### How It Works

| Token Algorithm | Verification Path |
| --------------- | ----------------- |
| RS256 | RSA public key from `spp_oauth` settings + audience/issuer/expiry validation |
| HS256 | Original `spp_api_v2` shared-secret verification (unchanged) |

The bridge replaces the `get_authenticated_client` FastAPI dependency via `dependency_overrides`. All existing API endpoints automatically support both algorithms — no router changes needed.

### Dependencies

| Module | Role |
| ------ | ---- |
| `spp_api_v2` | Provides the REST API, HS256 auth, and API client model |
| `spp_oauth` | Provides RSA key storage and retrieval utilities |

### Configuration

1. Configure RSA keys in **Settings > General Settings > SPP OAuth Settings**
2. The bridge activates automatically — existing HS256 clients continue to work unchanged
3. Use `/oauth/token/rs256` to obtain RS256-signed tokens
