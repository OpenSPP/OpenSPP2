### 19.0.2.0.1

- fix(security): restrict the OAuth signing keys (``oauth_priv_key``, ``oauth_pub_key``) to
  ``base.group_system``. The settings ACL row granting ``base.group_user`` access to
  ``res.config.settings`` is removed, and ``default_get()`` no longer returns the key values to
  non-system users. Deployments must treat the currently deployed RSA keypair as compromised:
  rotate it and invalidate outstanding tokens, because every internal user could previously read
  the private key.

### 19.0.2.0.0

- Initial migration to OpenSPP2
