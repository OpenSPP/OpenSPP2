### 19.0.2.0.2

- fix(api): an authorization failure on a change-request state transition now returns `403 Forbidden` instead of `409 Conflict`. `AccessError` subclasses `UserError` in Odoo, so the `$submit` / `$approve` / `$apply` / `$reset` endpoints — which caught `UserError` and returned a conflict — reported permission failures as conflicts. A client is then told to resolve a conflict it cannot see, and one that retries on 409 loops on a permission error that will never clear. Reachable on `$apply` in particular now that applying requires the change-request manager role, where the endpoint's own scope check already returned 403, so the same endpoint reported two authorization failures with different statuses.

### 19.0.2.0.1

- fix: skip field types before getattr and isolate detail prefetch (#129)

### 19.0.2.0.0

- Initial migration to OpenSPP2
