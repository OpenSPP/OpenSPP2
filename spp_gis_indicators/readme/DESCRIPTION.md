Choropleth visualization for area-level indicators on GIS maps. Maps indicator values from CEL variables to colors using configurable classification methods and ColorBrewer-based color scales. Supports quantile, equal interval, and manual break classification with automatic legend generation.

### Key Capabilities

- Define indicator layer configurations linking a CEL variable to a color scale and classification method
- Classify continuous values into discrete color classes using quantile, equal interval, or manual breaks
- Compute break values automatically from actual data distribution
- Generate HTML legends showing color-to-value mappings
- Map area features to colors for choropleth rendering in GIS data layers
- Filter indicators by period key and hazard incident context
- Ship 11 preset ColorBrewer color scales (5 sequential, 4 diverging, 2 categorical)

### Key Models

| Model                      | Description                                                          |
| -------------------------- | -------------------------------------------------------------------- |
| `spp.gis.indicator.layer`  | Configuration linking a CEL variable to color scale and class method |
| `spp.gis.color.scale`      | Color scheme definition with JSON array of hex colors                |
| `spp.gis.data.layer` (ext) | Extended with `indicator_layer_id` for choropleth rendering          |

### Configuration

After installing:

1. Navigate to **Settings > GIS Configuration > Color Scales**
2. Review the 11 preset ColorBrewer scales or create custom ones
3. Navigate to **Settings > GIS Configuration > Indicator Layers**
4. Create an indicator layer: select the CEL variable, period key, color scale, and classification method
5. In a GIS data layer form, set `geo_repr` to `choropleth` and select the indicator layer

### UI Location

- **Menu**: Settings > GIS Configuration > Indicator Layers
- **Menu**: Settings > GIS Configuration > Color Scales
- **Access**: Menus restricted to `base.group_system` (Settings/System admin)
- **Indicator form tabs**: Data Source, Visualization, Legend Preview

### Security

| Group                            | Color Scales | Indicator Layers |
| -------------------------------- | ------------ | ---------------- |
| `spp_registry.group_registry_read` | Read         | Read             |
| `spp_security.group_spp_admin`   | Full CRUD    | Full CRUD        |

### Extension Points

- Override `_compute_quantile_breaks()` or `_compute_equal_interval_breaks()` for custom classification algorithms
- Inherit `spp.gis.color.scale` and override `get_color_for_value()` for custom color mapping
- Extend `spp.gis.indicator.layer._get_indicator_values()` to support data sources beyond `spp.hxl.area.indicator`
- Override `spp.gis.data.layer._get_choropleth_config()` to customize frontend choropleth config

### Dependencies

`spp_gis`, `spp_hxl_area`, `spp_registry`, `spp_security`
