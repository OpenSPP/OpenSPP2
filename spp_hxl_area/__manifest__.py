# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP HXL Area Integration",
    "summary": "HXL import with area-level aggregation for humanitarian indicators. "
    "Import HXL-tagged field data and aggregate to area-level metrics for coordination.",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "development_status": "Beta",
    "depends": [
        "spp_hxl",
        "spp_area",
        "spp_cel_domain",
        "spp_hazard",
        "spp_security",
        "queue_job",
    ],
    "external_dependencies": {
        "python": [
            "libhxl",
        ]
    },
    "data": [
        "security/ir.model.access.csv",
        "views/hxl_import_profile_views.xml",
        "views/hxl_aggregation_rule_views.xml",
        "views/hxl_import_batch_views.xml",
        "views/hxl_area_indicator_views.xml",
        "wizards/hxl_area_import_wizard_views.xml",
        "data/hxl_import_profiles.xml",
        "views/menus.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
