{
    "name": "OpenSPP API V2 - Service Points",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_service_points",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "spp_service_points"],
    "summary": """
        REST API endpoints for Service Points.
    """,
    "description": """
OpenSPP API V2 - Service Points
================================

Extends OpenSPP API V2 with Service Point endpoints.

Endpoints
---------
- ``GET /ServicePoint`` - Search service points
- ``GET /ServicePoint/{identifier}`` - Read service point by name or ID

Design Principles
-----------------
- Uses service point name as external identifier
- Returns appropriate HTTP status codes
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
