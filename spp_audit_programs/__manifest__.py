# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{  # pylint: disable=pointless-statement
    "name": "OpenSPP Audit - Programs",
    "category": "OpenSPP/Core",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "summary": "Audit rules for program and cycle models.",
    "depends": [
        "spp_audit",
        "spp_programs",
    ],
    "data": [
        "data/audit_rule_data.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_audit", "spp_programs"],
}
