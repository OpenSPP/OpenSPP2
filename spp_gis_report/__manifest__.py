{
    "name": "OpenSPP GIS Reports",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Geographic visualization and reporting for social protection data",
    "description": """
OpenSPP GIS Report Module
=========================

This module enables non-technical users to create, configure, and view
geographic visualizations of social protection data.

Features:
---------
* Template-based report creation wizard
* Configurable data aggregation by administrative area
* Multiple normalization methods (per km², per capita, percentage)
* Hierarchical rollup to all administrative levels
* Color-blind safe palettes by default
* GeoJSON API for external tool integration (QGIS, Power BI)
* Scheduled and trigger-based data refresh

Pre-built Templates:
--------------------
* Coverage Analysis: Beneficiary density, coverage rate, gap analysis
* Disaster Response: Affected population, request status, fulfillment
* Demographics: Age, gender, disability distributions
    """,
    "author": "OpenSPP",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "depends": [
        "spp_area",
        "spp_gis",
        "spp_registry",
        "spp_vocabulary",
        "spp_cel_domain",
        "queue_job",
    ],
    "external_dependencies": {
        "python": ["numpy>=1.22.2", "shapely"],
    },
    "data": [
        # Security
        "security/privileges.xml",
        "security/groups.xml",
        "security/gis_report_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/gis_report_category_data.xml",
        "data/templates/coverage_templates.xml",
        "data/templates/disaster_templates.xml",
        "data/templates/demographic_templates.xml",
        "data/gis_report_cron.xml",
        # Views
        "views/gis_report_views.xml",
        "views/gis_report_data_views.xml",
        "views/gis_report_template_views.xml",
        "views/gis_report_category_views.xml",
        "views/data_layer_ext_views.xml",
        "views/area_views.xml",
        "views/menu.xml",
        # Wizards
        "wizards/gis_report_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_gis_report/static/src/css/gis_report.css",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
