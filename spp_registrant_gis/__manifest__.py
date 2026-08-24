# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Registrant GIS",
    "category": "OpenSPP",
    "version": "19.0.2.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "spp_gis",
        "spp_registry",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "Adds GPS coordinates to registrants for spatial queries",
}
