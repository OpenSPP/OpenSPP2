# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Child Benefit Demo",
    "category": "OpenSPP/Demo",
    "version": "19.0.1.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "summary": "Self-contained demo environment for the child benefit programme: "
    "installs all required modules and sets up the program, managers, and demo families.",
    "depends": [
        "spp_child_benefit",
        "spp_approval",
        "spp_area",
        "spp_audit",
        "spp_audit_programs",
        "spp_change_request_v2",
        "spp_cr_types_base",
        "spp_dms",
        "spp_grm",
        "spp_grm_registry",
        "spp_registry_search",
        "spp_user_roles",
        "theme_openspp_muk",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/grm_portal_security.xml",
        "data/demo_banks.xml",
        "data/demo_areas.xml",
        "data/demo_users.xml",
        "data/change_request_approval.xml",
        "data/grm_categories.xml",
        "data/demo_filters.xml",
        "views/res_config_settings_views.xml",
        "views/individual_views.xml",
        "views/grm_portal_templates.xml",
        "views/cr_portal_templates.xml",
        # Last: it moves the cards the two templates above add to the portal home.
        "views/portal_home_views.xml",
    ],
    "assets": {
        # Appended in module order, i.e. after spp_base_common's and the theme's
        # navbar stylesheets (both are dependencies), whose literal colours it re-points.
        "web.assets_backend": [
            "spp_demo_child_benefit/static/src/scss/backend_theme.scss",
        ],
        "web.assets_frontend": [
            "spp_demo_child_benefit/static/src/scss/frontend_theme.scss",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
