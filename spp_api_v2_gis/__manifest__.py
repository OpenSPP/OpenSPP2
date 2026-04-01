# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP GIS API",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_api_v2",
        "spp_gis",
        "spp_gis_report",
        "spp_area",
        "spp_hazard",
        "spp_vocabulary",
        "spp_indicator",
        "spp_analytics",
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
}
