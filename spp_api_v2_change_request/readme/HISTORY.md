### 19.0.2.0.3

- fix(api): error statuses on change-request endpoints are now consistent across the module and aligned with the platform's global FastAPI error handler. `ValidationError` on a state transition returns `422 Unprocessable Entity` (previously `409 Conflict`), matching what create and update already returned for the same condition — a missing rejection reason or revision notes is invalid input, not a conflict. `MissingError` returns `404 Not Found`. An authorization failure on create returns `403 Forbidden` (previously swallowed by the generic handler as a `500`). The `403` response body is now a fixed generic detail instead of the raw Odoo message, which named models and record rules (anti-enumeration).

### 19.0.2.0.2

- fix(api): an authorization failure on a change-request state transition now returns `403 Forbidden` instead of `409 Conflict`. `AccessError` subclasses `UserError` in Odoo, so all six state-transition endpoints — `$submit` / `$approve` / `$reject` / `$request-revision` / `$apply` / `$reset` — which caught `UserError` and returned a conflict, reported permission failures as conflicts. A client is then told to resolve a conflict it cannot see, and one that retries on 409 loops on a permission error that will never clear. Reachable on `$apply` in particular now that applying requires the change-request manager role, where the endpoint's own scope check already returned 403, so the same endpoint reported two authorization failures with different statuses. `AccessDenied` maps to 403 the same way, matching the platform's global FastAPI error handler.

### 19.0.2.0.1

- fix: skip field types before getattr and isolate detail prefetch (#129)

### 19.0.2.0.0

- Initial migration to OpenSPP2
