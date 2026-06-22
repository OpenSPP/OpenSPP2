# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Demo: Philippines Luzon Geodata",
    "category": "OpenSPP/Demo",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "summary": "Philippine Luzon administrative boundaries and population weights for demo data generation",
    "description": """
        Provides Philippine Luzon geodata for the OpenSPP demo generator.

        Includes area records for regions, provinces, and municipalities of Luzon,
        polygon shapes in GeoJSON format, and population weights for realistic
        geographic distribution of generated demo registrants.

        Administrative boundary data sourced from OCHA Humanitarian Data Exchange
        (HDX) COD-AB dataset. Source: PSA and NAMRIA. License: CC BY-IGO.
    """,
    "depends": ["spp_demo"],
    "data": [
        # Security
        "security/ir.model.access.csv",
    ],
    # Loaded programmatically (not at install): areas_luzon.xml via the area
    # loader's pre-link + convert_file step, population_weights.csv via
    # DemoPopulationWeights. Declared here so oca-checks knows they are used.
    "oca_data_manual": [
        "data/areas_luzon.xml",
        "data/population_weights.csv",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
