### 19.0.2.0.1

- fix: bind coordinate query parameters in the order the SQL expects
- fix: run the coordinate statistics query inside a savepoint so the area fallback stays reachable
- fix: run the coordinate proximity query inside a savepoint so the area fallback stays reachable
- fix: add `geofence` and `incident` scope actions so geofence endpoints can be granted

### 19.0.2.0.0

- Initial migration to OpenSPP2
