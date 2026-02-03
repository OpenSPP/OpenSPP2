{
    "name": "OpenSPP Studio - Change Requests",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "No-code change request type builder",
    "description": """
OpenSPP Studio - Change Requests
=================================

Provides a user-friendly interface for creating custom change request types
without code. Allows program staff to configure simple field-based change
requests with approval workflows.

Features:
- Visual CR type builder wizard (3 steps)
- Field selection and mapping
- Approval workflow configuration
- Draft/Active lifecycle for safe editing
- Auto-apply approved changes to registrants
- Integration with spp_change_request_v2 infrastructure

Target Use Cases:
- Address update requests
- Phone number changes
- Bank account updates
- Contact information changes
- Simple demographic updates
    """,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
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
