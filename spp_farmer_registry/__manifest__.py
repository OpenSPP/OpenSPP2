# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Farmer Registry",
    "summary": "Farmer Registry with vocabulary-based fields, CEL variables, and Logic Studio integration",
    "category": "OpenSPP",
    "version": "19.0.2.0.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        # Foundation
        "spp_registry",
        "spp_registry_search",
        "spp_security",
        "spp_area",
        # Vocabularies
        "spp_vocabulary",
        "spp_farmer_registry_vocabularies",
        # CEL & Studio
        "spp_cel_domain",
        "spp_studio",
        # Land & GIS (keep from V1)
        "spp_land_record",
        "spp_irrigation",
        "spp_gis",
        # OP#951 menu audit — roles get hazard / GIS reports menu access
        "spp_hazard",
        "spp_gis_report",
    ],
    "excludes": [
        "spp_base_farmer_registry",  # V1 module - incompatible _inherits definitions
    ],
    "external_dependencies": {"python": ["shapely", "geojson", "pyproj"]},
    "data": [
        "security/privileges.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/cel_variable_categories.xml",
        "data/cel_variables.xml",
        "data/cel_constants.xml",
        "data/config_parameters.xml",
        "data/user_roles.xml",
        "views/res_config_settings_views.xml",
        "views/farm_season_views.xml",
        "views/farm_details_views.xml",
        "views/farm_activity_views.xml",
        "views/farm_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_farmer_registry/static/src/js/registry_restriction.js",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "pre_init_hook": "pre_init_hook",
}
