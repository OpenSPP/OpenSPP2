### 19.0.2.0.2

- fix(security): make the OAuth2 token/header methods private so they are no longer callable over RPC — a low-privilege internal user can no longer mint a DCI access token or obtain a Bearer header via `get_oauth2_token()` / `get_headers()`. Restrict the token cache fields (`_oauth2_access_token` / `_oauth2_token_expires_at`) to system administrators, and require write access to run a connection test.

### 19.0.2.0.0

- Initial migration to OpenSPP2
