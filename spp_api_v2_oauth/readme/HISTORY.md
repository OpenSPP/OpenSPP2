## 19.0.2.0.0

Initial Production/Stable release.

- Auto-installing bridge between `spp_api_v2` and `spp_oauth` that adds RS256
  JWT authentication to API V2 alongside the existing HS256 path. Tokens are
  routed by the JWT header `alg`; RS256 tokens are further dispatched by `iss`
  so OpenSPP can accept tokens from external Identity Providers (e.g. Keycloak)
  registered as `spp.oauth.issuer` records.
- New endpoint `POST /oauth/token/rs256` for internally-issued RS256 tokens
  (mirrors `/oauth/token` for HS256: same client-credentials flow, rate
  limiting, and payload shape).
- New admin model `spp.oauth.issuer` (Settings → API V2 → Trusted OAuth
  Issuers) for registering external IdPs by `iss` value, with JWKS-URI or
  static-PEM key sources, configurable client claim, algorithm whitelist, and
  process-local JWKS caching.
- `spp.api.client.oauth_issuer_id` links an API client to a Trusted OAuth
  Issuer. Internal HS256 / internal RS256 tokens only resolve to clients with
  no issuer link; external-issuer tokens only resolve to clients linked to the
  matching issuer record. Prevents external IdPs from authenticating as
  internal clients via colliding claim values.
- 30-second clock-skew leeway on RS256 verification (`exp` / `nbf` / `iat`) to
  absorb normal NTP drift between OpenSPP and external IdPs.
- Algorithm allowlist enforced at both the issuer-record level (constraints
  reject HMAC algorithms and `none` at write time) and the JWT verification
  level (explicit `algorithms=` argument on every `jwt.decode`).
- JWKS URIs are constrained to `https://` (loopback `http://` allowed for dev
  IdPs); static PEMs are validated with `cryptography.load_pem_public_key` at
  write time so private-key paste mistakes are caught immediately.
