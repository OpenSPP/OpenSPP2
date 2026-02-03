# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Security",
    "summary": "Central security definitions for OpenSPP modules",
    "category": "OpenSPP/Core",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": ["base"],
    "data": [
        "security/categories.xml",
        "security/privileges.xml",
        "security/groups_admin.xml",
        "security/rules_base.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
