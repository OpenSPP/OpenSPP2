### 19.0.2.0.1

- fix(security): restrict storage backend credentials to storage administrators.
  The S3 access/secret keys and Azure connection string were readable by any
  internal user via RPC (`base.group_user` had model read and the fields had no
  field-level protection). The three credential fields are now gated with
  `groups="spp_storage_backend.group_storage_admin"`, and the S3/Azure client
  builders resolve them via `sudo()` so a non-admin can still operate a backend
  without being able to read the secret.

### 19.0.2.0.0

- Initial migration to OpenSPP2
