{
    "name": "OpenSPP Studio",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "No-code customization interface for OpenSPP",
    "description": """
OpenSPP Studio
==============

A no-code customization interface designed for semi-technical users at NGOs
and UN agencies. Enables program staff to configure OpenSPP without developer
involvement.

Features:
- CEL Expression Editor: Full CEL expression editor for creating business logic
- Variable Dictionary: Integrated discovery of all available variables
- Logic Packs: Pre-built formula bundles for common use cases
- Custom Fields: Add custom fields to Individual/Group registries
- Testing: Built-in test cases and personas

This module consolidates:
- spp_studio_fields (merged)
- spp_studio_logic (merged)

Target Users:
- Program Data Managers
- M&E Officers
- Country Coordinators
    """,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Stable",
    "depends": [
        "base",
        "mail",
        "spp_audit",
        "spp_security",
        "spp_registry",
        "spp_base_common",
        "spp_programs",
        "spp_user_roles",
        "spp_custom_field",
        "spp_cel_domain",  # Unified variable system
        "spp_cel_widget",
        "spp_vocabulary",
        "spp_approval",
        "spp_versioning",  # Version history with scheduled activation
    ],
    "data": [
        # Security (must be first)
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        # Data files
        "data/vocabularies.xml",
        "data/placement_zones.xml",
        "data/server_actions.xml",
        "data/audit_rules.xml",
        "data/user_roles.xml",
        "data/variable_categories.xml",
        "data/standard_variables.xml",
        "data/default_personas.xml",
        # Logic packs
        "data/packs/cash_transfer_basic.xml",
        "data/packs/pmt_targeting.xml",
        "data/packs/child_benefit.xml",
        "data/packs/social_pension.xml",
        "data/packs/disability_assistance.xml",
        "data/packs/ovc_support.xml",
        "data/packs/cct_program.xml",
        "data/packs/vulnerability_assessment.xml",
        "data/packs/geographic_targeting.xml",
        "data/packs/guaranteed_minimum_income.xml",
        "data/packs/public_works.xml",
        "data/packs/benefit_adjustments.xml",
        "data/packs/exclusion_criteria.xml",
        # Views
        "views/dashboard_views.xml",
        "views/studio_field_views.xml",
        "views/logic_views.xml",
        "views/logic_variable_views.xml",
        "views/logic_test_views.xml",
        "views/logic_pack_views.xml",
        # Wizards (before menus, as menus reference wizard actions)
        "views/deactivate_wizard_views.xml",
        "views/field_builder_wizard_views.xml",
        "views/pack_install_wizard_views.xml",
        "views/variable_install_wizard_views.xml",
        "views/variable_remap_wizard_views.xml",
        # Menus (last, after all actions are defined)
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_studio/static/src/css/field_builder_wizard.css",
            "spp_studio/static/src/scss/logic_studio.scss",
            "spp_studio/static/src/css/variable_picker.css",
            "spp_studio/static/src/js/**/*",
            "spp_studio/static/src/xml/**/*",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "sequence": 1,
}
