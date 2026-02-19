# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Base Settings",
    "category": "OpenSPP/Core",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "depends": [
        "spp_security",
        "base",
        "spp_registry",
    ],
    "data": [
        "views/country_office_views.xml",
        # "views/res_users_views.xml",
    ],
    "oca_data_manual": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "OpenSPP Base Setting provides fundamental configurations for country implementations, establishing core organizational structures such as Country Offices. It also enables tailored user interface adaptations and streamlines user management by linking individuals to specific Country Offices for context-aware data access.",
}
