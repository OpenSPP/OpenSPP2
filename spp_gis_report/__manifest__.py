{
    "name": "OpenSPP GIS Reports",
    "version": "19.0.2.1.0",
    "category": "OpenSPP",
    "summary": "Geographic visualization and reporting for social protection data",
    "author": "OpenSPP.org, OpenSPP",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "depends": [
        "spp_area",
        "spp_gis",
        "spp_metric_service",
        "spp_registry",
        "spp_vocabulary",
        "spp_cel_domain",
        "job_worker",
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
        "data/user_roles.xml",
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
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
