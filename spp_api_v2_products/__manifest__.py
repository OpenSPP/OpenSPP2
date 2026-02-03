# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP API V2 - Products",
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
        "product",
        "uom",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "product"],
    "summary": """
        REST API endpoints for Products, Categories, and Units of Measure.
    """,
    "description": """
OpenSPP API V2 - Products
==========================

Extends OpenSPP API V2 with Product-related endpoints.

Endpoints
---------
- ``GET /Product`` - Search products
- ``GET /Product/{identifier}`` - Read product by code or name
- ``GET /ProductCategory`` - List product categories
- ``GET /UnitOfMeasure`` - List units of measure

Design Principles
-----------------
- Uses product default_code or name as external identifier
- Returns appropriate HTTP status codes
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
