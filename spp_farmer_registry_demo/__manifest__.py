# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Farmer Registry Demo",
    "summary": "Demo generator for Farmer Registry with fixed stories and volume generation",
    "category": "OpenSPP",
    "version": "19.0.2.1.5",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
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
        # GIS / land / irrigation — used by Scenario 10 (FM4 GIS+irrigation walk)
        "spp_gis",
        "spp_land_record",
        "spp_irrigation",
        # Registrant GIS — adds the Location/coordinates group on the Profile
        # tab; our view inherits move it to the end of the tab.
        "spp_registrant_gis",
        # FAO vocabularies — surface AGROVOC species selection in scenarios
        "spp_farmer_registry_vocabularies",
    ],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "data/demo_users.xml",
        "data/approval_definitions.xml",
        "data/approval_links.xml",
        "data/demo_personas.xml",
        "data/demo_programs.xml",
        "data/logic_packs.xml",
        "data/disable_group_types.xml",
        "data/service_types.xml",
        "views/farmer_demo_wizard_view.xml",
        "views/group_form_overrides.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
