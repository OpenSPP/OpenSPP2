### Prerequisites

- `spp_api_v2` and `spp_oauth` modules installed (bridge auto-installs)
- RSA key pair generated and configured in SPP OAuth Settings
- An API client created in `spp_api_v2` with appropriate scopes

### Generate RSA Keys

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
```

Configure the keys in **Settings > General Settings > SPP OAuth Settings**.

### Obtain an RS256 Token

```bash
curl -X POST https://your-instance/api/v2/spp/oauth/token/rs256 \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "client_abc123",
    "client_secret": "your-client-secret"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "scope": "individual:read group:read"
}
```

### Use the Token

```bash
curl https://your-instance/api/v2/spp/Individual/urn:test%23ID-001 \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

The API automatically detects RS256 tokens from the JWT header and verifies them with the configured RSA public key.

### Existing HS256 Clients

No changes needed. Tokens obtained from the original `/oauth/token` endpoint continue to work. The bridge accepts both RS256 and HS256 tokens simultaneously, routing based on the `alg` field in the JWT header.

### Accepting Tokens from an External Identity Provider

OpenSPP can be configured to accept RS256 tokens issued by an external IdP (e.g., a Keycloak realm) so deployments can integrate with an existing organizational identity provider. The bridge dispatches by the JWT `iss` claim: each `iss` value points to one **Trusted OAuth Issuer** record, which provides the verification key (JWKS URI or static PEM) and the claim that resolves the calling API client.

1. **Create a Trusted OAuth Issuer record** under **API V2 > Trusted OAuth Issuers** (admin-only). Required fields:
   - **Issuer** — exact value the IdP puts in `iss` (e.g. `https://keycloak.example.com/realms/openspp`).
   - **Audience** — the value the IdP puts in `aud` for tokens targeted at OpenSPP.
   - **Key Source** — either *JWKS URI* (preferred; supports key rotation) or *Static Public Key (PEM)*.
   - **JWKS URI** — must be `https://` (plain `http://` is rejected except for `localhost` / `127.0.0.1` dev IdPs).
   - **Client Claim** — the JWT claim whose value must equal the existing `spp.api.client.client_id`. Defaults to `client_id`; for Keycloak service accounts, `azp` or `sub` is typical.

2. **Match the Client Claim value to an existing API Client.** Set `spp.api.client.client_id` to the value the IdP emits in the configured claim. The bridge looks the client up by that exact value.

3. **Request a token from the external IdP**, then call OpenSPP with it:

   ```bash
   curl https://your-instance/api/v2/spp/Individual/urn:test%23ID-001 \
     -H "Authorization: Bearer <token from external IdP>"
   ```

The bridge:
- Reads `iss` from the unverified payload.
- If `iss` matches the internal openspp-api-v2 issuer, uses the spp_oauth key (existing behavior).
- Otherwise looks up the matching active `spp.oauth.issuer` record and verifies with its JWKS or static PEM.
- Reads the configured `client_claim` from the verified payload and resolves the `spp.api.client`.

### Example External IdP: Keycloak Realm

| Field            | Value                                                                        |
| ---------------- | ---------------------------------------------------------------------------- |
| Name             | `Org Keycloak`                                                               |
| Issuer           | `https://keycloak.example.org/realms/openspp`                                |
| Audience         | `openspp-api` (configure an audience mapper in Keycloak to emit this value)  |
| Key Source       | `JWKS URI`                                                                   |
| JWKS URI         | `https://keycloak.example.org/realms/openspp/protocol/openid-connect/certs` |
| Algorithms       | `RS256`                                                                      |
| Client Claim     | `azp` (Keycloak's "authorized party" — the client_id of the service account) |

JWKS responses are cached in process memory for `JWKS Cache TTL Seconds` (default 3600). Editing or archiving the record drops the cached client; the next request rebuilds it.

### Verify Token Algorithm

To confirm which algorithm a token uses, decode the JWT header (without verification):

```python
import jwt
header = jwt.get_unverified_header(token)
# header["alg"] will be "RS256" or "HS256"
```

### Error Responses

| Scenario | HTTP Status | Detail |
| -------- | ----------- | ------ |
| RSA keys not configured | 400 | "RS256 token generation not available..." |
| Invalid credentials | 401 | "Invalid client credentials" |
| Expired token | 401 | "Token expired" |
| Invalid signature | 401 | "Invalid token" |
| Unsupported algorithm | 401 | "Unsupported token algorithm: {alg}" |
| Missing `iss` claim | 401 | "Invalid token: missing iss claim" |
| Unknown / inactive external issuer | 401 | "Untrusted issuer" |
| Rate limit exceeded | 429 | "Rate limit exceeded" |
