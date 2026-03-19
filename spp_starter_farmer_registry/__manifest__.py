# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Starter: Farmer Registry",
    "summary": "Complete Farmer Registry bundle with API, DCI, and Program support",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
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
    "description": """
OpenSPP Starter: Farmer Registry
================================

A comprehensive bundle for Farmer Registry deployments. This module installs
all necessary components for a production-ready farmer registry system with
program management capabilities.

Included Capabilities
---------------------
- **Registry Management**: Track farmers, farms, and households
- **FAO Vocabularies**: ICC crops, FAO livestock, ASFIS aquaculture species
- **Agricultural Activities**: Season-based activity tracking
- **Land Records**: GIS-enabled land parcel management
- **Irrigation**: Water access and irrigation tracking
- **CEL Variables**: Farm metrics for Logic Studio eligibility rules
- **Program Management**: Subsidies, grants, and cash transfers
- **API V2**: Standards-aligned REST API with consent-based access
- **DCI Integration**: Connect to external registries (CRVS, IBR, DR)
- **Change Requests**: Data maintenance workflows

Use Cases
---------
- National Farmer Registries
- Agricultural Input Subsidy Programs
- Livestock Development Programs
- Climate Adaptation Support
- Farm Equipment Grants

Configuration
-------------
Key configuration parameters:
- ``spp.farmer.smallholder_threshold``: Maximum hectares for smallholder status (default: 5.0)

The smallholder threshold varies by region:
- Sub-Saharan Africa: 2 hectares (FAO recommendation)
- South Asia: 2 hectares
- Southeast Asia: 3 hectares
- Latin America: 5-10 hectares

For a Social Registry without farmer-specific features, use ``spp_starter_social_registry`` instead.
    """,
}
