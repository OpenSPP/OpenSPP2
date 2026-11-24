### 19.0.2.0.5

- fix(security): reject non-ASCII Bearer tokens with a 401 instead of raising an
  unhandled error. A Bearer token carrying non-ASCII header bytes reached
  ``hmac.compare_digest`` as a non-ASCII string, which raises ``TypeError`` and
  surfaced as a generic 500 (with a stack trace) on public DCI endpoints. Such
  tokens are now rejected before the constant-time comparison.

### 19.0.2.0.4

- Return signed DCI ``on-search`` envelopes from registry alias stubs (disability, crvs, farmer) instead of HTTP 501; per-item ``rjct`` with ``ACTION_NOT_SUPPORTED``.

### 19.0.2.0.0

- Initial migration to OpenSPP2
