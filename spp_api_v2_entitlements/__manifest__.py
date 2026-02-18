# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP API V2 - Entitlements",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
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
}
