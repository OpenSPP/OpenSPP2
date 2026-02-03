# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Hide Non-OpenSPP Menus: Base",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "summary": "Administrators can manage the visibility of OpenSPP navigation menus, streamlining the user interface for specific user groups. The module modifies ir.ui.menu records to control menu visibility, providing a foundation for other modules to selectively hide non-essential navigation items.",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["emjay0921", "jeremi"],
    "depends": ["base", "spp_security"],
    "data": [
        "security/privileges.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/hide_menu_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
