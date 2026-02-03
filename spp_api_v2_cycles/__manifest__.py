# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{  # pylint: disable=pointless-statement
    "name": "OpenSPP API V2 - Cycles",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "spp_programs"],
    "summary": """
        REST API endpoints for Program Cycles.
    """,
    "description": """
OpenSPP API V2 - Cycles
========================

Extends OpenSPP API V2 with Cycle endpoints.

Endpoints
---------
- ``GET /Cycle`` - Search cycles
- ``GET /Cycle/{identifier}`` - Read cycle by name

Design Principles
-----------------
- Uses cycle name as external identifier
- Returns appropriate HTTP status codes
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
