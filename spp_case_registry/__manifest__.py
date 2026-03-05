# pylint: disable=pointless-statement
{
    "name": "OpenSPP Case Registry Integration",
    "category": "OpenSPP/Monitoring",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "spp_case_base",
        "spp_registry",
        "spp_area",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/case_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": True,
}
