# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{  # pylint: disable=pointless-statement
    "name": "OpenSPP Studio - Programs",
    "category": "OpenSPP/Configuration",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "summary": "Program scoping for OpenSPP Studio configurations.",
    "depends": [
        "spp_studio",
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
    "auto_install": ["spp_studio", "spp_programs"],
}
