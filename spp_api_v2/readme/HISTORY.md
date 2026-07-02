### 19.0.2.1.0

- Add OpenAPI polymorphic schema utilities (`utils/openapi_polymorphic.py`): `polymorphic_body()` for declaring dict-typed fields that accept one of several Pydantic models, plus an app-level OpenAPI hook that injects the corresponding `anyOf` schemas into the generated document
- Auth middleware: replace the plain `HTTPBearer` scheme with an OAuth2 client-credentials security scheme so the OpenAPI document advertises the token endpoint and consumers (Swagger UI, QGIS, etc.) can discover how to authenticate; strip the `Bearer` prefix from the raw Authorization header value
- Bundle schemas: document `BundleEntry.resource` as a polymorphic Individual/Group body instead of an opaque dict, so bundle payloads are fully described in the OpenAPI document
- Add OpenAPI contract tests covering bundle schema rendering, the polymorphic utilities, and the overall OpenAPI document contract

### 19.0.2.0.1

- Fix `SerializationFailure` race when multiple Odoo workers rebuild their routing map simultaneously (e.g. after `-u all`) and all try to sync the same `fastapi.endpoint` rows
- Serialize concurrent sync attempts across workers using a transaction-scoped Postgres advisory lock; workers that don't acquire the lock skip the sync and pick up the freshly synced routes on the next routing-map rebuild (via `endpoint_route_version` cache invalidation)
- Log skipped syncs at INFO and lock-primitive failures at WARNING so cold-start route-availability symptoms and broken-primitive regressions are diagnosable without raising the global log level

### 19.0.2.0.0

- Initial migration to OpenSPP2
