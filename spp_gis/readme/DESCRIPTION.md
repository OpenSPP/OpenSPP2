PostGIS integration for geospatial data management, map visualization, and spatial querying. Adds geo field types (point, line, polygon) to any model, renders interactive maps with configurable layers, and enables location-based searches. Extends `spp.area` with coordinate and polygon fields.

### Key Capabilities

- Define geo fields (`geo_point`, `geo_line`, `geo_polygon`) on any model using PostGIS spatial types
- Visualize records on interactive maps via the GIS view type
- Configure background raster layers (OpenStreetMap, WMS, satellite imagery)
- Configure data layers with basic or choropleth (color-by-value) rendering
- Perform spatial queries (intersects, contains, within, distance-based) via `gis_locational_query()`
- Import area boundaries from GeoJSON/shapefiles via area import wizard
- Manage color schemes for thematic mapping with sequential, diverging, or qualitative palettes

### Key Models

| Model                         | Description                                                |
| ----------------------------- | ---------------------------------------------------------- |
| `spp.gis.raster.layer`        | Background map layers (OSM, WMS, image)                    |
| `spp.gis.data.layer`          | Vector data layers referencing geo fields from any model   |
| `spp.gis.color.scheme`        | Color palettes for choropleth and thematic visualizations  |
| `spp.gis.raster.layer.type`   | Raster layer type definitions (WMS services)               |

### Configuration

After installing:

1. PostGIS extension is initialized automatically via pre-init hook
2. Add geo fields to models via **Settings > Technical > Database Structure > Fields**
3. Create GIS views via **Settings > Technical > User Interface > Views** with type "GIS"
4. Configure map layers on GIS views by adding raster (background) and data (vector) layers

### UI Location

- **GIS View**: Available as a view mode on models with geo fields (e.g., `spp.area`)
- **Area Form**: "Coordinates" and "Polygon" tabs appear when editing areas (Social Protection > Configuration > Areas)
- **No standalone menu**: This module does not define menu items; GIS functionality is accessed through existing models

### Security

| Group                                  | Access                                        |
| -------------------------------------- | --------------------------------------------- |
| `spp_security.group_spp_admin`         | Full CRUD on all GIS models                   |
| `spp_registry.group_registry_read`     | Read-only on color schemes and layers         |
| `spp_gis.group_gis_user`               | View GIS data and maps                        |
| `spp_gis.group_gis_admin`              | Full GIS management including configuration   |

### Extension Points

- Inherit `base` and call `gis_locational_query(longitude, latitude, layer_type, spatial_relation)` for location-based searches
- Override `_get_choropleth_config()` on `spp.gis.data.layer` to customize thematic mapping logic
- Inherit any model and add `geo_point`, `geo_line`, or `geo_polygon` fields to enable spatial storage
- Create GIS views by setting `type="gis"` in `ir.ui.view` XML and linking `spp.gis.data.layer` records

### Dependencies

`base`, `web`, `contacts`, `spp_security`, `spp_area`

External Python libraries: `shapely`, `pyproj`, `geojson`
