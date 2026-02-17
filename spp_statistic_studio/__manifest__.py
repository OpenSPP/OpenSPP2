# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Statistics Studio",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "Studio UI for managing publishable statistics",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "spp_statistic",
        "spp_studio",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/statistic_views.xml",
        "views/statistic_category_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    # Bridge module: auto-install when both spp_statistic and spp_studio are present
    "auto_install": ["spp_statistic", "spp_studio"],
}
