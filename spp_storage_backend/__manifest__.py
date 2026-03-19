# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Storage Backend",
    "summary": "Pluggable storage backend configuration for OpenSPP file storage",
    "category": "OpenSPP/Core",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "base",
        "spp_security",
    ],
    "data": [
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/storage_backend_views.xml",
        "data/storage_backend_data.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
