Extends registrants with GPS coordinates for spatial queries and geographic analysis. Adds a PostGIS point field to both individuals and groups, enabling proximity-based targeting and mapping.

### Key Capabilities

- Store latitude/longitude coordinates on any registrant (individual or group)
- Query registrants by geographic location using PostGIS spatial operators
- Visualize registrant locations on maps via GIS widgets

### Key Models

This module extends existing models, no new models added:

| Model         | Extension                         |
| ------------- | --------------------------------- |
| `res.partner` | Adds `coordinates` GeoPointField |

### UI Location

- **Individual Form**: Located in Profile tab under "Location" section (after phone numbers)
- **Group Form**: Located in Profile tab under "Location" section (after phone numbers)
- Field is read-only when registrant is disabled

### Security

No new models or security groups. Uses existing `res.partner` permissions from `spp_registry`.

### Technical Details

- Field type: `fields.GeoPointField` (from `spp_gis`)
- Storage: PostGIS POINT geometry with SRID 4326 (WGS84)
- Supports spatial operators: `gis_intersects`, `gis_within`, `gis_contains`, `gis_distance`, etc.
- Widget: `geo_point` for coordinate input/display

### Dependencies

`spp_gis`, `spp_registry`
