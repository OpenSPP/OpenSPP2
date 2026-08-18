### 19.0.2.0.1

- fix(security): restrict the OAuth signing keys (``oauth_priv_key``, ``oauth_pub_key``) to
  ``base.group_system``. The settings ACL row granting ``base.group_user`` access to
  ``res.config.settings`` is removed, and ``default_get()`` no longer returns the key values to
  non-system users. Deployments must treat the currently deployed RSA keypair as compromised:
  rotate it and invalidate outstanding tokens, because every internal user could previously read
  the private key.
- fix(security): field-gate the signing keys with ``groups="base.group_system"`` so a settings
  save by an unauthorized principal fails with ``AccessError`` instead of silently deleting the
  stored key parameters (``set_param(False)`` unlinks them), and so ``read``/``search`` on the
  fields is denied independently of the model ACL.
- fix: restore ``@api.model`` on the ``default_get()`` override. Without it, external RPC calls
  to ``res.config.settings.default_get`` (for any module's settings) crashed with a ``TypeError``
  once this module was installed; the web Settings UI was unaffected.

### 19.0.2.0.0

- Initial migration to OpenSPP2
