# pylint: disable=pointless-statement
{
    "name": "OpenSPP Branding Kit",
    "version": "19.0.2.0.1",
    "summary": "Branding customization, URL routing and telemetry management for OpenSPP",
    "author": "OpenSPP.org, OpenSPP Project",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "category": "OpenSPP/Configuration",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_security",
        "base",
        "web",
        "base_setup",
        "theme_openspp_muk",  # Required for OpenSPP styling
    ],
    "data": [
        "security/ir.model.access.csv",
        # Default configuration data (order matters)
        "data/res_company_data.xml",
        "data/ir_config_parameter.xml",
        "data/debranding_data.xml",
        # Views - UI customizations
        "views/webclient_templates.xml",
        "views/login_templates.xml",
        "views/report_templates.xml",
        "views/backend_customization.xml",
        "views/res_config_settings_views.xml",
        "views/about_settings.xml",
        "views/ir_module_module_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_branding_kit/static/src/js/webclient.js",
            "spp_branding_kit/static/src/js/user_menu.js",
            "spp_branding_kit/static/src/js/router_patch.js",
        ],
        "web.assets_frontend": [
            "spp_branding_kit/static/src/css/login_branding.css",
        ],
    },
    "images": [
        "static/description/icon.png",
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": ["base", "web"],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
