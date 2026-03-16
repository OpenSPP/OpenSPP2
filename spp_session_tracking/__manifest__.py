# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Session Tracking",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "base",
        "mail",
        "spp_area",
        "spp_security",
    ],
    "data": [
        "security/privileges.xml",
        "security/session_security.xml",
        "security/session_rules.xml",
        "security/ir.model.access.csv",
        "data/session_data.xml",
        "views/session_type_views.xml",
        "views/session_views.xml",
        "views/session_menus.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "Track attendance at required sessions and trainings for social protection programs",
}
