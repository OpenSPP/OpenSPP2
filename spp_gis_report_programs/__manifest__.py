{
    "name": "OpenSPP GIS Reports - Programs Integration",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Add program context filtering to GIS reports",
    "author": "OpenSPP.org, OpenSPP",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "spp_gis_report",
        "spp_programs",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/gis_report_views.xml",
        "views/gis_report_wizard_views.xml",
    ],
    "development_status": "Beta",
    "installable": True,
    "application": False,
    "auto_install": True,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
