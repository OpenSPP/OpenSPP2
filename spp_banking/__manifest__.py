# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Banking: Bank Details",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "depends": [
        "spp_security",
        "base",
        "mail",
        "contacts",
        "spp_registry",
    ],
    "external_dependencies": {"python": ["schwifty"]},
    "data": [
        "security/ir.model.access.csv",
        "views/individuals_view.xml",
        "views/groups_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
