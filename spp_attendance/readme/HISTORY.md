### 19.0.2.0.0

- Initial migration from openspp-modules
- fix(security): store API client secrets as scrypt hashes instead of plaintext. Secrets are shown
  once at creation/regeneration and can no longer be read back afterwards — including secrets that
  existed before the upgrade, which a migration hashes in place. Clients keep authenticating with
  their unchanged secrets. The Attendance Viewer group's read access to the credential model is
  removed.
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
