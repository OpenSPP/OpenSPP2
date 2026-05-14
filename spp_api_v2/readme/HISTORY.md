### 19.0.2.0.1

- Fix `SerializationFailure` race when multiple Odoo workers rebuild their routing map simultaneously (e.g. after `-u all`) and all try to sync the same `fastapi.endpoint` rows
- Serialize concurrent sync attempts across workers using a transaction-scoped Postgres advisory lock; workers that don't acquire the lock skip the sync and pick up the freshly synced routes on the next routing-map rebuild (via `endpoint_route_version` cache invalidation)
- Log skipped syncs at INFO and lock-primitive failures at WARNING so cold-start route-availability symptoms and broken-primitive regressions are diagnosable without raising the global log level

### 19.0.2.0.0

- Initial migration to OpenSPP2
