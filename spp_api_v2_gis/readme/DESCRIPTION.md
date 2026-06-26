REST API for QGIS plugin integration, providing OGC API - Features endpoints, spatial queries, and geofence management.

## Key Features

- **OGC API - Features**: Standards-compliant feature collections (GovStack GIS BB)
- **GeoJSON Export**: Get pre-aggregated layer data for QGIS
- **QML Styling**: Fetch QGIS style files for consistent visualization
- **Spatial Queries**: Query registrant statistics within arbitrary polygons using PostGIS
- **Geofence Management**: Save and manage areas of interest

## Architecture

Follows thin client architecture where QGIS displays data and OpenSPP performs all computation:

- All spatial queries executed in PostGIS for performance (including bbox via ST_Intersects)
- Pre-aggregated data returned to minimize data transfer
- Configuration-driven styling using QML templates
- JWT authentication with scope-based access control

## API Endpoints

**OGC API - Features**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gis/ogc/` | GET | OGC API landing page |
| `/gis/ogc/conformance` | GET | OGC conformance classes |
| `/gis/ogc/collections` | GET | List feature collections |
| `/gis/ogc/collections/{id}` | GET | Collection metadata |
| `/gis/ogc/collections/{id}/items` | GET/POST | Feature items (GeoJSON) |
| `/gis/ogc/collections/{id}/items/{fid}` | GET/PUT/DELETE | Single feature (CRUD for geofences) |
| `/gis/ogc/collections/{id}/qml` | GET | QGIS style file (extension) |

**OGC API - Processes**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gis/ogc/processes` | GET | List available processes |
| `/gis/ogc/processes/{id}` | GET | Process description |
| `/gis/ogc/processes/{id}/execution` | POST | Execute process (sync/async) |
| `/gis/ogc/jobs` | GET | List jobs |
| `/gis/ogc/jobs/{id}` | GET/DELETE | Job status / dismiss |
| `/gis/ogc/jobs/{id}/results` | GET | Job results |

**Utility endpoints**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gis/export/geopackage` | GET | Export for offline use |
| `/gis/statistics` | GET | List published statistics |

## Scopes and Data Privacy

**OAuth Scopes**

| Scope | Access | Description |
|-------|--------|-------------|
| `gis:read` | Read-only | View collections, layers, statistics, export data |
| `gis:geofence` | Read + Write | Create and archive geofences (also requires `gis:read` for listing) |

**What data is exposed**

**Aggregated statistics only.** No endpoint in this module returns individual registrant records.

- **OGC collections/items**: Return GeoJSON features organized by administrative area, with pre-computed aggregate values (counts, percentages). Each feature represents an *area*, not a person.
- **Spatial query statistics** (via OGC Processes): Accepts a GeoJSON polygon and returns configured aggregate statistics computed by `spp.analytics.service`. Individual registrant IDs are computed internally for aggregation but are **explicitly stripped** from the response before it is sent.
- **Exports** (GeoPackage/GeoJSON): Contain the same area-level aggregated layer data, not registrant-level records.
- **Geofences**: Store only geometry and metadata — no registrant data.

**Privacy controls**

- **K-anonymity suppression**: Statistics backed by CEL variables can apply k-anonymity thresholds. When a cell count falls below the configured minimum, the value is replaced with a suppression marker and flagged as `"suppressed": true` in the response. This prevents re-identification in small populations.
- **CEL variable configuration**: Administrators control which statistics are published and their suppression thresholds via `spp.indicator` records.
- **Scope separation**: `gis:read` and `gis:geofence` are separate scopes, allowing clients to be granted read-only access without write capability.

**Design rationale**

This module follows a **thin client** architecture: QGIS (or any OGC-compatible client) displays pre-aggregated data, while OpenSPP retains all individual-level data server-side. This ensures that GIS API clients — including the QGIS plugin — never need access to personally identifiable information.

## Dependencies

- `spp_api_v2` - FastAPI infrastructure
- `spp_gis` - PostGIS integration
- `spp_gis_report` - Report configuration
- `spp_area` - Administrative area data
