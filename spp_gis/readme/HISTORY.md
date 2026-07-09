### 19.0.2.1.0

- feat: spatial operators support MultiPolygon and GeometryCollection, including distance buffering (re-land from #76).
- feat: OSM style fallback in map renderer/edit widgets when no MapTiler API key is configured; placeholder key treated as unconfigured (re-land from #76).
- feat: geofence GeoJSON output includes the record uuid as feature id; new `spp.gis.geofence.tag` model replaces vocabulary-based geofence tags (re-land from #76).
- feat: migration remaps existing vocabulary-based geofence tag links onto `spp.gis.geofence.tag` records when upgrading from 19.0.2.0.x.

### 19.0.2.0.0

- Initial migration to OpenSPP2
