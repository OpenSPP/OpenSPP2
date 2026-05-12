# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Registry Search Portal",
    "category": "OpenSPP/Registry",
    "version": "19.0.2.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "summary": "Search-first registry interface for privacy protection",
    "depends": [
        "spp_registry",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/config_parameters.xml",
        "views/res_config_settings_views.xml",
        "views/registry_search_actions.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_registry_search/static/src/js/registry_search_portal.js",
            "spp_registry_search/static/src/js/hide_archive_form.js",
            "spp_registry_search/static/src/xml/registry_search_portal.xml",
            "spp_registry_search/static/src/css/registry_search.css",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
