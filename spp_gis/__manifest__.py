# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

# pylint: disable=pointless-statement
{
    "name": "OpenSPP GIS",
    "category": "OpenSPP/Core",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": ["base", "web", "contacts", "spp_security", "spp_area", "spp_registry"],
    "external_dependencies": {"python": ["shapely", "pyproj", "geojson"]},
    "data": [
        "data/res_config_data.xml",
        "data/color_scheme_data.xml",
        "security/privileges.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/ir_model_view.xml",
        "views/ir_view_view.xml",
        "views/raster_layer_view.xml",
        "views/data_layer_view.xml",
        "views/color_scheme_views.xml",
        "views/area.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Use wildcard to load all GIS assets after web core
            # The 'web' dependency ensures web.assets_backend loads first
            "spp_gis/static/src/js/**/*",
            "spp_gis/static/src/css/**/*",
        ]
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "init_postgis",
    "summary": "GIS core plus area geo fields and importer extensions (points/polygons, layers, spatial queries).",
}
