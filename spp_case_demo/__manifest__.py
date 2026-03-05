# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Case Management Demo Data",
    "version": "19.0.1.0.0",
    "category": "OpenSPP",
    "summary": "Demo data generator for Case Management",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_demo",  # Consolidated demo module
        "spp_case_base",
        "spp_security",
    ],
    "external_dependencies": {"python": ["faker"]},
    "data": [
        "security/ir.model.access.csv",
        "data/case_types.xml",
        "data/case_stages.xml",
        "views/case_demo_wizard_view.xml",
    ],
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
