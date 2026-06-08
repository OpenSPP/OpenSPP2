Digitizes land parcel information and links it to farms, owners, and lessees. Captures geographical boundaries using GeoPoint and GeoPolygon fields, classifies land use, and tracks lease agreements. Exports GeoJSON for external GIS analysis.

### Key Capabilities

- Store land parcel details including name, acreage, and use classification
- Capture geospatial data via point coordinates and polygon boundaries
- Link parcels to farms, owners, and lessees through `res.partner` relationships
- Track lease agreements with start and end dates
- Export land records as GeoJSON with configurable SRID transformation

### Key Models

| Model             | Description                                            |
| ----------------- | ------------------------------------------------------ |
| `spp.land.record` | Stores land parcel details, geospatial data, and links |

### UI Location

No dedicated menu views are provided. Access land records through related farm or registrant profiles, or via custom views in extending modules.

### Security

| Group                                 | Access                          |
| ------------------------------------- | ------------------------------- |
| `spp_security.group_spp_admin`        | Full CRUD                       |
| `spp_registry.group_registry_officer` | Full CRUD                       |
| `spp_registry.group_registry_read`    | Read                            |
| `spp_registry.group_registry_write`   | Read/Write/Delete (no create)   |
| `spp_registry.group_registry_create`  | Read/Create (no write or delete) |

### Extension Points

- Override `_process_record_to_feature()` to customize GeoJSON feature generation
- Override `_get_search_domain_by_geometry_type()` to filter land records by geometry type
- Inherit `spp.land.record` to add domain-specific fields (e.g., soil type, irrigation status)

### Dependencies

`base`, `spp_base_common`, `spp_gis`, `spp_registry`, `spp_security`
