# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP GRM Demo Data",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Demo data generator for Grievance Redress Mechanism",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_demo",  # Consolidated demo module
        "spp_grm",
        "spp_security",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "data/ticket_categories.xml",
        "views/grm_demo_wizard_view.xml",
    ],
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
