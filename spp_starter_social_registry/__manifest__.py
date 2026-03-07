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
    "development_status": "Production/Stable",
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
        "job_worker",
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
}
