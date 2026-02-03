# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP API V2 - Entitlements",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.0",
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
        REST API endpoints for Entitlements (Cash and In-Kind).
    """,
    "description": """
OpenSPP API V2 - Entitlements
==============================

Extends OpenSPP API V2 with Entitlement endpoints.

Endpoints
---------
- ``GET /Entitlement`` - Search entitlements
- ``GET /Entitlement/{identifier}`` - Read entitlement by code

Design Principles
-----------------
- Uses entitlement code (UUID) as external identifier
- Supports both cash and in-kind entitlements
- Returns appropriate HTTP status codes
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
