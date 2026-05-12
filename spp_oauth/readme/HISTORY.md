### 19.0.2.1.0

- refactor: rename config parameters `spp_oauth.oauth_priv_key` → `spp_oauth.oauth_private_key` and `spp_oauth.oauth_pub_key` → `spp_oauth.oauth_public_key`, and the model class `RegistryConfig` → `OAuthConfig`, per naming conventions. Update any deployment that reads these parameters directly.
- fix: empty the placeholder default values for the OAuth key config parameters so `get_private_key()` / `get_public_key()` raise a clear `OpenSPPOAuthJWTException` when keys are not configured, instead of failing later with a cryptic PyJWT error on the placeholder strings.
- feat: export `get_private_key` and `get_public_key` from `spp_oauth.tools` for use by downstream modules.
- security: restrict the OAuth Settings ACL to `base.group_system`.
- chore: remove ERROR logging from `OpenSPPOAuthJWTException`'s constructor (callers decide whether to log).

### 19.0.2.0.0

- Initial migration to OpenSPP2
