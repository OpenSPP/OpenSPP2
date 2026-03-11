Choropleth visualization for area-level indicators on GIS maps. Maps indicator values from CEL variables to colors using configurable classification methods and ColorBrewer-based color scales. Supports quantile, equal interval, and manual break classification with automatic legend generation.

### Key Capabilities

- Define indicator layer configurations that link CEL variables to color scales and classification methods
- Classify continuous indicator values into discrete color classes using quantile, equal interval, or manual breaks
- Apply preset ColorBrewer color scales (sequential, diverging, categorical) or define custom scales
- Compute break values automatically based on actual data distribution
- Generate HTML legends showing color-to-value mappings
- Map area features to colors for choropleth rendering in GIS data layers
- Filter indicators by period and hazard incident context

### Key Models

- **spp.gis.indicator.layer** -- Configuration linking a CEL variable to color scale and classification settings
- **spp.gis.color.scale** -- Color scheme definition with JSON array of hex colors
- **spp.gis.data.layer** -- Extended with choropleth geo representation option

### Configuration

After installing:

1. Navigate to **Settings > GIS Configuration > Color Scales**
2. Review preset ColorBrewer scales (Blues, Greens, Red-Yellow-Green, etc.) or create custom scales
3. Navigate to **Settings > GIS Configuration > Indicator Layers**
4. Create an indicator layer specifying the CEL variable, period key, color scale, and classification method
5. In an existing GIS data layer, set `geo_repr` to `choropleth` and select the indicator layer to visualize

### UI Location

- **Menu**: Settings > GIS Configuration > Indicator Layers
- **Menu**: Settings > GIS Configuration > Color Scales

### Security

- **spp_security.group_spp_user** -- Read
- **spp_security.group_spp_manager** -- Read/write/create (no delete)
- **spp_security.group_spp_admin** -- Full CRUD

### Extension Points

- Override `_compute_quantile_breaks()` or `_compute_equal_interval_breaks()` in `spp.gis.indicator.layer` to add custom classification algorithms
- Inherit `spp.gis.color.scale` and override `get_color_for_value()` to implement custom color mapping logic
- Extend `spp.gis.indicator.layer._get_indicator_values()` to support additional data sources beyond `spp.hxl.area.indicator`

### Dependencies

`spp_gis`, `spp_hxl_area`, `spp_registry`, `spp_security`
