### 19.0.2.0.1

- fix: bind coordinate query parameters in the order the SQL expects
- fix: run the coordinate statistics query inside a savepoint so the area fallback stays reachable
- fix: run the coordinate proximity query inside a savepoint so the area fallback stays reachable
- fix: run the area fallback queries inside savepoints so a failed geometry cannot abort the transaction
- fix: run each batch geometry and the batch summary inside savepoints so one failed geometry cannot poison the rest of the batch
- fix: propagate statistics failures instead of mislabelling them as coordinate-query failures and retrying via the area fallback
- fix: add `geofence` and `incident` scope actions so geofence endpoints can be granted (`incident` prepares for the incidents API re-land)

### 19.0.2.0.0

- Initial migration to OpenSPP2
