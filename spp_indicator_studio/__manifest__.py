# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Indicator Studio",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "Studio UI for managing publishable indicators",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "spp_indicator",
        "spp_studio",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/indicator_views.xml",
        "views/indicator_category_views.xml",
        "views/menus.xml",
    ],
    "development_status": "Beta",
    "installable": True,
    # Bridge module: auto-install when both spp_indicator and spp_studio are present
    "auto_install": True,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
