# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Base (Common)",
    "category": "OpenSPP/Core",
    "version": "19.0.1.3.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "base",
        # "theme_openspp_muk",  # Removed for Odoo 19 Community Edition compatibility
        "spp_user_roles",
        "spp_hide_menus_base",
        "spp_base_setting",
        "spp_registry",
        "spp_security",
    ],
    "excludes": [],
    "external_dependencies": {},
    "data": [
        "data/global_roles.xml",
        "data/local_roles.xml",
        "security/security_access.xml",
        "security/ir.model.access.csv",
        "views/main_view.xml",
        "views/phone_validation_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_base_common/static/src/scss/navbar.scss",
        ],
        "web._assets_primary_variables": [
            "spp_base_common/static/src/scss/colors.scss",
            "spp_base_common/static/src/scss/colors_light.scss",
        ],
        "web.assets_web_dark": ["spp_base_common/static/src/scss/colors_dark.scss"],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "The OpenSPP base module that provides the main menu, generic configuration, user role management base module, area management base module, hiding of non-openspp menus. All implementation specific base modules depends on this module. (Odoo 19 Community Edition - uses default theme)",
}
