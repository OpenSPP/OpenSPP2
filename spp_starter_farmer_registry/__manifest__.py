# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Starter: Farmer Registry",
    "summary": "Complete Farmer Registry bundle with API, DCI, and Program support",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        # Social Registry Foundation (includes registry, security, area, vocabulary, etc.)
        "spp_starter_social_registry",
        # Farmer-specific modules
        "spp_farmer_registry",
        "spp_farmer_registry_vocabularies",
        # Land & GIS
        "spp_land_record",
        "spp_irrigation",
        "spp_gis",
        # Programs for subsidies and grants (includes entitlements)
        "spp_programs",
    ],
    "data": [
        "data/config_parameters.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
