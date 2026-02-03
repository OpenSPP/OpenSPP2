Generates geographic reports by aggregating social protection data to administrative areas and rendering them as choropleth maps. Users create reports from pre-built templates via a wizard, configure normalization methods, and define color thresholds. Computed data is cached for fast rendering and refreshed on schedule via queue_job. Exposes GeoJSON API for external tool integration.

### Key Capabilities

- Template-based wizard guides users through report creation with three steps
- Aggregates registrant, program, or disaster data by administrative area using configurable field paths
- Normalizes values per km², per capita, per household, or as percentages
- Rolls up data through area hierarchy from base level to all parent levels
- Auto-calculates thresholds using quartiles, equal intervals, Jenks breaks, or standard deviation
- Scheduled or on-demand data refresh with background job processing
- GeoJSON API endpoints using report codes (not database IDs) for external tools
- Supports multiple geometry types: polygon choropleth, point markers, clusters, heatmaps

### Key Models

| Model                      | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| `spp.gis.report`           | Report configuration defining source, aggregation, and display |
| `spp.gis.report.data`      | Cached computed values for each area, updated on schedule      |
| `spp.gis.report.template`  | Pre-built report definitions with JSON configuration           |
| `spp.gis.report.category`  | Categories for organizing reports and templates                |
| `spp.gis.report.threshold` | Color threshold definitions for map visualization              |
| `spp.gis.report.wizard`    | Three-step wizard for creating reports from templates          |

### Configuration

No configuration required after installation. Pre-built templates are loaded automatically and accessible via the wizard.

### UI Location

- **Menu**: GIS Reports > Reports
- **Templates**: GIS Reports > Templates
- **Configuration**: GIS Reports > Configuration > Categories and Color Schemes (admin only)
- **Wizard**: Create reports by opening a template and clicking "Create Report"
- **Form Tabs**: General, Data Source, Aggregation, Normalization, Visualization, Rollup, Schedule, Access, Map Layer

### Security

| Group                                 | Access                              |
| ------------------------------------- | ----------------------------------- |
| `base.group_user`                     | Read reports and data               |
| `group_gis_report_user`               | Read reports, write data for refresh|
| `group_gis_report_officer`            | Read/Write/Create (no delete)       |
| `group_gis_report_manager`            | Full CRUD                           |
| `spp_registry.group_registry_officer` | Read reports and data               |
| `spp_security.group_spp_admin`        | Full CRUD and configuration         |

### API Endpoints

All endpoints use report `code` as identifier, not database IDs:

- `GET /api/v2/GISReport` - List available reports
- `GET /api/v2/GISReport/<code>/geojson` - Get report data as GeoJSON FeatureCollection
- `GET /api/v2/GISReport/<code>/summary` - Get aggregate statistics
- `POST /api/v2/GISReport/<code>/refresh` - Trigger manual data refresh

### Extension Points

- Override `_get_gis_report_source_models()` on `spp.gis.report` to add models as data sources
- Override `_apply_context_filters()` on `spp.gis.report` to add module-specific filtering (e.g., program context)
- Inherit `spp.gis.report.wizard` and override `_validate_context_requirements()` and `_get_context_filter_vals()` to add wizard steps for program or incident selection
- Add report templates via data XML files with JSON configuration
- Extend `spp.area` to add reference data fields for normalization

### Dependencies

`spp_area`, `spp_gis`, `spp_registry`, `spp_vocabulary`, `spp_cel_domain`, `queue_job`
