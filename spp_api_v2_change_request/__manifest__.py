{  # pylint: disable=pointless-statement
    "name": "OpenSPP API V2 - Change Request",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
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
}
