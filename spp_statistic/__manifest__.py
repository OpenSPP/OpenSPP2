# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Statistics",
    "summary": "Publishable statistics based on CEL variables for dashboards, GIS, and APIs",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_cel_domain",
        "spp_metrics_core",
        "spp_security",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/statistic_categories.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
