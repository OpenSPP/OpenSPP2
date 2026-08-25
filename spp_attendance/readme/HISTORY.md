### 19.0.2.0.0

- Initial migration to OpenSPP2
- fix(security): store API client secrets as scrypt hashes instead of plaintext. Each secret is
  shown once via the Show Credentials dialog and cannot be read back after that display (until the
  dialog is used, the stored plaintext remains readable by attendance managers). Secrets that
  existed before the upgrade are hashed in place by a migration. Clients keep authenticating with
  their unchanged secrets. The Attendance Viewer group's read access to the credential model is
  removed.
- fix(security): the one-time credential display wizard is readable only by the user who opened
  it — previously any attendance manager could read a secret another manager had just issued
- fix: the REST API works on Odoo 19 again — every response with a body crashed with
  `AttributeError` because `date_utils.json_default` was removed from Odoo
- fix: gender is never fabricated as "Male" — the res.partner field default, the subscriber
  related-field default, the registry-import fallback and the subscriber-create fallback all
  stamped it when gender was unknown; the value now comes only from source data
- fix(wizard): a missing sync-configuration parameter raises the intended error message instead of
  crashing with `KeyError`; access tokens already carrying a `Basic` scheme are no longer
  double-prefixed
- fix(wizard): registry sync requests carry a 30s timeout so a hung remote registry cannot freeze
  the worker
