# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Farmer Registry Demo",
    "summary": "Demo generator for Farmer Registry with fixed stories and volume generation",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        # Farmer Registry Starter Bundle
        "spp_starter_farmer_registry",
        # Demo Infrastructure
        "spp_demo",
        # Change Request Types
        "spp_farmer_registry_cr",
        # Logic Studio for Logic Packs
        "spp_studio",
        # Group Hierarchy
        "spp_registry_group_hierarchy",
        # Areas (explicitly used for area_id assignment)
        "spp_area",
        # Programs (explicitly used for cycles, entitlements, payments)
        "spp_programs",
    ],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "data/demo_users.xml",
        "data/approval_links.xml",
        "data/demo_personas.xml",
        "data/demo_programs.xml",
        "data/logic_packs.xml",
        "views/farmer_demo_wizard_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Farmer Registry Demo
============================

Demo generator for the Farmer Registry with fixed stories and random volume generation.

Demo Features
-------------
- **Fixed Story Farms**: 8 farmer personas with complete data
- **Random Volume**: Additional farms for realistic dashboards
- **Demo Programs**: Input Subsidy, Equipment Grant, Livestock Support
- **Agricultural Seasons**: Active season with activities
- **FAO Vocabularies**: Crops, livestock, and aquaculture species

Demo Personas
-------------
1. Maria Santos - 2ha rice farmer, female
2. Juan Dela Cruz - 3ha mixed farm (rice + vegetables)
3. Rosa Garcia - 1ha + 20 goats, female-headed
4. Amir Mangudadatu - 4ha drought-affected (BARMM)
5. Sofia Martinez - 2ha transitioning organic
6. Ramon dela Cruz - 0.5ha fishpond
7. Sittie Pangandaman - 1.5ha, female head (BARMM)
8. Danilo Villanueva - 5ha, mixed commercial
    """,
}
