# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP GIS Indicators",
    "summary": "Choropleth visualization for area-level indicators",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/GIS",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "depends": [
        "spp_gis",
        "spp_hxl_area",
        "spp_registry",
        "spp_security",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/color_scales.xml",
        "views/menu.xml",
        "views/indicator_layer_views.xml",
        "views/color_scale_views.xml",
        "views/data_layer_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
