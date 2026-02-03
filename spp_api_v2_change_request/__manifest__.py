{  # pylint: disable=pointless-statement
    "name": "OpenSPP API V2 - Change Request",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_change_request_v2",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/fastapi_endpoint.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "spp_change_request_v2"],
    "summary": """
        REST API endpoints for Change Request V2.
    """,
    "description": """
OpenSPP API V2 - Change Request
================================

Extends OpenSPP API V2 with Change Request endpoints.

Endpoints
---------
- ``POST /ChangeRequest`` - Create a new change request
- ``GET /ChangeRequest/{identifier}`` - Read a change request by reference
- ``GET /ChangeRequest`` - Search change requests
- ``PATCH /ChangeRequest/{identifier}`` - Update change request detail data
- ``POST /ChangeRequest/{identifier}/$submit`` - Submit for approval
- ``POST /ChangeRequest/{identifier}/$approve`` - Approve (requires permission)
- ``POST /ChangeRequest/{identifier}/$reject`` - Reject (requires permission)
- ``POST /ChangeRequest/{identifier}/$apply`` - Apply changes to registrant

Design Principles
-----------------
- Uses CR reference (CR/2024/00001), NOT database IDs
- Returns appropriate HTTP status codes
- Follows OpenSPP API V2 patterns
- Requires authentication via OAuth 2.0
    """,
}
