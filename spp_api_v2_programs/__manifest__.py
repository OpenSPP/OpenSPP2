# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{  # pylint: disable=pointless-statement
    "name": "OpenSPP API V2 - Programs",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "summary": "REST API endpoints for Programs and Program Memberships.",
    "depends": [
        "spp_api_v2",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/api_path_data.xml",
        "data/filter_config_program.xml",
        "data/filter_config_program_membership.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": ["spp_api_v2", "spp_programs"],
}
