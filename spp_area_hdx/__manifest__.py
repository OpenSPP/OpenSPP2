# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP HDX COD Integration",
    "summary": "HDX Common Operational Datasets (COD) integration for downloading "
    "admin boundaries with polygons. Supports humanitarian coordination with "
    "P-code standardization and GPS-based area lookup.",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.0",
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_area",
        "spp_gis",
    ],
    "external_dependencies": {
        "python": [
            "requests",
            "geojson",
        ]
    },
    "data": [
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/hdx_cod_sources.xml",
        "views/hdx_cod_source_views.xml",
        "views/hdx_cod_resource_views.xml",
        "views/area_views.xml",
        "wizards/hdx_cod_import_wizard_views.xml",
        "views/menus.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
