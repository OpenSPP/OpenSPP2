### 19.0.2.0.0

- Initial migration from openspp-modules
- fix(security): store API client secrets as scrypt hashes instead of plaintext. Secrets are shown
  once at creation/regeneration and can no longer be read back afterwards — including secrets that
  existed before the upgrade, which a migration hashes in place. Clients keep authenticating with
  their unchanged secrets. The Attendance Viewer group's read access to the credential model is
  removed.
- fix: `gender_char` on `res.partner` no longer defaults to "Male"
