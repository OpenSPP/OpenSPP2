# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Registry",
    "category": "OpenSPP/Core",
    "version": "19.0.2.2.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "summary": "Consolidated registry management for individuals, groups, and membership",
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
        # res_config_settings_views.xml defines menu_registry_settings_root, which
        # main_view.xml reparents the Configuration menu under (OP#1009), so it
        # must load first.
        "views/res_config_settings_views.xml",
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
            "spp_registry/static/src/js/x2many_no_padding_field.js",
        ],
    },
    "oca_data_manual": [
        "data/id_types.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
