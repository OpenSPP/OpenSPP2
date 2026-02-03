# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Demo",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "summary": "Core demo module with data generator and sample data for OpenSPP",
    "description": """
OpenSPP Demo
============

This module consolidates core demo functionality for OpenSPP, including:

- Demo data generator with locale-specific providers
- Sample user data
- Demo stories for realistic test scenarios
- Configuration settings for demo generation

Features:
- Locale providers for Kenya (en_KE, sw_KE), Laos (lo_LA), Sri Lanka (si_LK, ta_LK)
- Configurable demo data generation

This module provides the foundation for domain-specific demo modules:
- spp_base_farmer_registry_demo (farmer-specific demo data)
- spp_case_demo (case management demo data)
- spp_grm_demo (GRM demo data)
- spp_event_demo (event demo data)
- spp_mis_demo_v2 (MIS programs and indicators demo data)
    """,
    "depends": [
        "base",
        "spp_base_common",
        "spp_registry",
        "spp_vocabulary",
        "queue_job",
        "spp_security",
    ],
    "external_dependencies": {
        "python": ["faker"],
    },
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Data
        "data/users_data.xml",
        "data/ir_config_parameter_data.xml",
        "data/res_country.xml",
        # Views
        "views/res_config_view.xml",
        "views/demo_data_generator_view.xml",
        # Wizards
        "wizard/apps_wizard_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
