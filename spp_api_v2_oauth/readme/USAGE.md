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
| Rate limit exceeded | 429 | "Rate limit exceeded" |
