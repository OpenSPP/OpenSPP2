### 19.0.2.0.2

- test(api_v2_gis): the "export with no data raises" test deactivates every `spp.gis.report` and `spp.gis.geofence` in the database, not only the ones it created. With an empty `layer_ids` the export collects all active reports, and a demo module in the same database (`spp_mis_demo_v2` ships four report records as data) supplied layers, so the expected error never came. No behaviour change (#443)

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
