# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP DRIMS - Sri Lanka Demo",
    "summary": "Demo data generator for DRIMS Sri Lanka implementation. "
    "Creates sample incidents, donations, requests, and stock for demonstrations.",
    "category": "OpenSPP/Inventory",
    "version": "19.0.2.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_drims_sl",
        "spp_area_hdx",
        # GIS Reports for geographic visualization
        "spp_gis_report",
    ],
    "external_dependencies": {"python": ["faker"]},
    "data": [
        "security/ir.model.access.csv",
        "data/demo_products.xml",
        "data/demo_users.xml",
        "data/demo_gis_reports.xml",
        "wizard/demo_generator_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
