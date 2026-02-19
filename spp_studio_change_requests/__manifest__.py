{
    "name": "OpenSPP Studio - Change Requests",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "No-code change request type builder",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "depends": [
        "spp_studio",
        "spp_change_request_v2",
        "spp_registry",
        "spp_audit",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Data
        "data/audit_rules.xml",
        # Views
        "views/studio_cr_type_views.xml",
        "views/menus.xml",
        # Wizards
        "wizard/cr_type_wizard_views.xml",
        "wizard/clone_type_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
