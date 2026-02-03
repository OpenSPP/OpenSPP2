# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Registry",
    "category": "OpenSPP/Core",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "summary": "Consolidated registry management for individuals, groups, and membership",
    "description": """
OpenSPP Registry
================

This module consolidates the core registry management system for OpenSPP, including:
- Base registry functionality for registrants
- Individual and group registry
- Group membership management
- Enhanced UI with improved UX
- Registrant tagging capabilities

Features:
- Comprehensive registrant management (individuals and groups)
- ID document tracking and verification
- Relationship management between registrants
- Group membership with roles and dates
- Flexible tagging system for categorization
- Consolidated tab structure (Profile, Identity, Participation, History)
- Enhanced list views with avatars and status badges
- Improved search and filtering
    """,
    "depends": [
        "base",
        "mail",
        "contacts",
        "web",
        "portal",
        "phone_validation",
        "spp_security",
        "spp_vocabulary",
        "muk_web_chatter",  # For the chatter default position
    ],
    "external_dependencies": {
        "python": [
            "python-magic",
        ]
    },
    "data": [
        # Data files
        "data/ir_model_data_aliases.xml",
        "data/ir_config_params.xml",
        # "data/id_types.xml",
        "data/vocabularies.xml",
        "data/res_users.xml",
        # Security
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        # Wizards
        "wizard/disable_registrant_view.xml",
        # Views - Base
        "views/main_view.xml",
        "views/reg_relationship_view.xml",
        "views/reg_id_view.xml",
        "views/id_types_view.xml",
        "views/phone_number_view.xml",
        "views/tags_view.xml",
        # Views - UI enhancements (must load before views that inherit from them)
        "views/individual_views.xml",
        "views/group_views.xml",
        # Views - Groups and Membership
        "views/group_membership_views.xml",
        "views/group_membership_view.xml",
        "views/membership_rules.xml",
        # Views - Individuals
        "views/individual_membership_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_registry/static/src/xml/custom_web.xml",
            "spp_registry/static/src/css/form_view_fix.css",
            "spp_registry/static/src/css/registry.css",
            "spp_registry/static/src/css/registry_form.css",
            "spp_registry/static/src/js/form_text_overflow.js",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
