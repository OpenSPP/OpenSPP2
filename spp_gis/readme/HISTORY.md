### 19.0.2.1.1

- test(gis): the geofence GeoJSON properties test asserts the core keys are present and no longer asserts that the incident keys are absent. `spp_api_v2_gis` legitimately adds `incident_id`/`incident_name` to the same properties (and asserts their presence in its own tests), so the absence check failed on every database carrying both modules. No behaviour change (#443)

### 19.0.2.1.0

- feat: spatial operators support MultiPolygon and GeometryCollection, including distance buffering (re-land from #76).
- feat: OSM style fallback in map renderer/edit widgets when no MapTiler API key is configured; placeholder key treated as unconfigured (re-land from #76).
- feat: geofence GeoJSON output includes the record uuid as feature id; new `spp.gis.geofence.tag` model replaces vocabulary-based geofence tags (re-land from #76).
- feat: migration remaps existing vocabulary-based geofence tag links onto `spp.gis.geofence.tag` records when upgrading from 19.0.2.0.x.

### 19.0.2.0.0

- Initial migration to OpenSPP2
