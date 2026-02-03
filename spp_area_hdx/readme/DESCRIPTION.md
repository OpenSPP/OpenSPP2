Downloads administrative boundary datasets from the Humanitarian Data Exchange (HDX) Common Operational Datasets (COD) platform and imports them into OpenSPP areas with polygon geometries. Extends `spp.area` with P-code fields for humanitarian coordination and provides GPS-based area lookup using PostGIS spatial queries.

### Key Capabilities

- Sync COD dataset metadata from HDX API by country
- Auto-detect field mappings from GeoJSON (P-code, name, parent P-code) using HXL tags
- Import admin boundaries with polygons from HDX or manually uploaded GeoJSON files
- Match imported features to existing areas by P-code or create new areas
- GPS-based area lookup using PostGIS `ST_Contains` for point-in-polygon queries
- Standardize area identification with HDX P-codes for inter-agency coordination

### Key Models

| Model                         | Description                                                   |
| ----------------------------- | ------------------------------------------------------------- |
| `spp.hdx.cod.source`          | Tracks COD datasets available from HDX (one per country)      |
| `spp.hdx.cod.resource`        | Individual admin level dataset within a COD (e.g., Level 3)   |
| `spp.hdx.cod.import.wizard`   | Multi-step wizard to download from HDX or upload GeoJSON      |
| `spp.area` (extended)         | Adds `hdx_pcode` field and GPS lookup methods                 |

### Configuration

After installing:

1. Navigate to **Area > Areas > HDX Integration > COD Sources**
2. Create a new COD Source, select a country
3. Click **Sync from HDX** to fetch available admin level resources from HDX API
4. Review detected resources under the **Admin Levels** tab
5. Click **Detect Field Mappings** on each resource to auto-detect P-code and name fields
6. Use **Import COD** menu to run the import wizard

### UI Location

- **Menu**: Area > Areas > HDX Integration > COD Sources
- **Import**: Area > Areas > HDX Integration > Import COD
- **Area Records**: Extended with HDX P-code field visible in area form view

### Security

| Group                        | Access                                                      |
| ---------------------------- | ----------------------------------------------------------- |
| `group_hdx_user`             | Read access to COD sources and resources                    |
| `group_hdx_manager`          | Full CRUD on sources/resources, sync from HDX, run imports  |

### Extension Points

- `spp.area.find_by_coordinates(latitude, longitude, level=None)` - Find area containing GPS point
- `spp.area.find_all_containing(latitude, longitude)` - Find all areas in hierarchy containing point
- `spp.area.find_by_pcode(pcode)` - Find area by HDX P-code or fallback to code field
- Inherit `spp.hdx.cod.source` to add country-specific dataset discovery logic
- Inherit `spp.hdx.cod.import.wizard._process_features()` to customize import behavior

### Dependencies

`spp_area`, `spp_gis`
