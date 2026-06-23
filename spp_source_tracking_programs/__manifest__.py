# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{  # pylint: disable=pointless-statement
    "name": "OpenSPP Source Tracking - Programs",
    "category": "OpenSPP/Core",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "summary": "Source tracking for program memberships.",
    "depends": [
        "spp_source_tracking",
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
    "auto_install": ["spp_source_tracking", "spp_programs"],
}
