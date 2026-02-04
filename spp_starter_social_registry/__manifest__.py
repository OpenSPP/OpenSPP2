# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Starter: Social Registry",
    "summary": "Complete Social Registry bundle with API, DCI, and Change Request support",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        # Core Registry
        "spp_registry",
        "spp_registry_search",
        # Security & Governance
        "spp_security",
        # Geographic & Vocabulary
        "spp_area",
        "spp_vocabulary",
        # Data Management
        "spp_consent",
        "spp_source_tracking",
        # Async Processing
        "queue_job",
        # Change Request System
        "spp_change_request_v2",
        "spp_cr_types_base",
        # Expression Engine & No-Code UI
        "spp_cel_domain",
        "spp_studio",
        # API V2
        "spp_api_v2",
        "spp_api_v2_data",
        # Note: spp_api_v2_vocabulary auto-installs with spp_api_v2 + spp_vocabulary
        # Note: spp_api_v2_change_request auto-installs with spp_api_v2 + spp_change_request_v2
        # DCI Client Integration
        "spp_dci_client",
        "spp_dci_client_crvs",
        "spp_dci_client_ibr",
        "spp_dci_client_dr",
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
OpenSPP Starter: Social Registry
================================

A comprehensive bundle for Social Registry deployments. This module installs
all necessary components for a production-ready social registry system.

Included Capabilities
---------------------
- **Registry Management**: Track individuals and groups (households)
- **Change Requests**: Base CR types (Edit Individual/Group, Update ID) for data maintenance
- **API V2**: Standards-aligned REST API with consent-based access
- **DCI Integration**: Connect to external registries (CRVS, IBR, DR)
- **Logic Studio**: No-code CEL expressions for search and filtering
- **Vocabularies**: Standardized code lists (gender, relationships, etc.)

Use Cases
---------
- National Social Registries
- Humanitarian Registration Systems
- Population Databases
- ID Management Systems (without program enrollment)

For SP-MIS with program management, use ``spp_starter_sp_mis`` instead.
    """,
}
