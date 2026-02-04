# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP API V2 - Data",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_cel_domain",
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
        REST API endpoints for Variable Data push/pull.
    """,
    "description": """
OpenSPP API V2 - Data
=====================

Extends OpenSPP API V2 with Variable Data management endpoints.

Endpoints
---------
- ``POST /Data/push`` - Push variable values from external systems
- ``GET /Data/pull`` - Pull variable values for subjects
- ``POST /Data/invalidate`` - Invalidate cached values
- ``GET /Data/variables`` - List available variables

Design Principles
-----------------
- Uses external identifiers, NOT database IDs
- Provider-based access control
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
