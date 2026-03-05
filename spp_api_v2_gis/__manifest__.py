# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP GIS API",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_gis",
        "spp_gis_report",
        "spp_area",
        "spp_hazard",
        "spp_vocabulary",
        "spp_statistic",
        "spp_aggregation",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": """
        OGC API - Features compliant GIS endpoints for QGIS and GovStack GIS BB.
    """,
    "description": """
OpenSPP GIS API
===============

Extends OpenSPP API V2 with OGC API - Features compliant endpoints,
enabling GovStack GIS Building Block compliance and interoperability
with any OGC client (QGIS, ArcGIS, Leaflet, ogr2ogr, etc.).

OGC API - Features Endpoints
-----------------------------
- ``GET /gis/ogc/`` - Landing page
- ``GET /gis/ogc/conformance`` - Conformance declaration
- ``GET /gis/ogc/collections`` - List feature collections
- ``GET /gis/ogc/collections/{id}`` - Collection metadata
- ``GET /gis/ogc/collections/{id}/items`` - Feature items (GeoJSON)
- ``GET /gis/ogc/collections/{id}/items/{fid}`` - Single feature
- ``GET /gis/ogc/collections/{id}/qml`` - QGIS style file (extension)

Proprietary Endpoints
---------------------
- ``POST /gis/query/statistics`` - Spatial statistics query
- ``CRUD /gis/geofences`` - Manage saved areas of interest
- ``GET /gis/export/geopackage`` - Export layers for offline use

Design Principles
-----------------
- OGC API - Features Core + GeoJSON conformance
- Thin client architecture (QGIS displays, OpenSPP computes)
- Pre-aggregated data for performance
- PostGIS spatial queries
- Requires authentication via OAuth 2.0
    """,
}
