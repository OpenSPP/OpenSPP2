{
    "name": "OpenSPP GIS Reports - Programs Integration",
    "version": "19.0.1.0.0",
    "category": "OpenSPP",
    "summary": "Add program context filtering to GIS reports",
    "description": """
GIS Reports Programs Integration
================================

This module automatically installs when both spp_gis_report and spp_programs
are installed. It adds:

* program_id field to GIS reports for filtering by program
* Program context filtering in report data aggregation
* View extensions to show program selector
    """,
    "author": "OpenSPP",
    "website": "https://github.com/OpenSPP/openspp-modules",
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
    "installable": True,
    "application": False,
    "auto_install": True,
}
