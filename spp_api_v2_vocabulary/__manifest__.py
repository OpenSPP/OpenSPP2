# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP API V2 - Vocabulary",
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
        "spp_vocabulary",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "spp_vocabulary"],
    "summary": """
        REST API endpoints for Vocabulary lookup.
    """,
    "description": """
OpenSPP API V2 - Vocabulary
===========================

Extends OpenSPP API V2 with Vocabulary lookup endpoints.

Endpoints
---------
- ``GET /Vocabulary`` - List all vocabularies
- ``GET /Vocabulary/{namespace_uri}/codes`` - Get codes for a vocabulary

Design Principles
-----------------
- Uses namespace URI as identifier, NOT database IDs
- Vocabularies are public (no consent required)
- Supports filtering and pagination
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
