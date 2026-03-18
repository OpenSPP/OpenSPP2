# pylint: disable=pointless-statement
{
    "name": "CEL Registry Search",
    "summary": "Search the registry using CEL expressions",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "development_status": "Stable",
    "author": "OpenSPP.org, OpenSPP Community",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "category": "OpenSPP",
    "depends": [
        "spp_registry",
        "spp_cel_domain",
        "spp_cel_widget",
    ],
    "data": [
        "security/groups.xml",
        "views/cel_search_portal.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_cel_registry_search/static/src/css/cel_search_portal.css",
            "spp_cel_registry_search/static/src/js/cel_search_portal.js",
            "spp_cel_registry_search/static/src/xml/cel_search_portal.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
