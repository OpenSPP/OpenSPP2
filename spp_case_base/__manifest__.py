# pylint: disable=pointless-statement
{
    "name": "OpenSPP Case Management Base",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Core case management functionality for OpenSPP",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "base",
        "mail",
        "portal",
        "spp_security",
    ],
    "data": [
        # Security
        "security/privileges.xml",
        "security/groups.xml",
        "security/case_security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        # Data
        "data/ir_cron.xml",
        # Views - load actions first, then main case view that references them
        "views/case_stage_views.xml",
        "views/case_type_views.xml",
        "views/case_assessment_views.xml",
        "views/case_intervention_views.xml",
        "views/case_activity_views.xml",
        "views/case_config_views.xml",
        "views/case_views.xml",
        # Menus
        "views/case_menus.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
