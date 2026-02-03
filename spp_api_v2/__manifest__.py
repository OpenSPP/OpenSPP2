{
    "name": "OpenSPP API V2",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "depends": [
        "base",
        "fastapi",
        "spp_security",
        "spp_registry",
        "spp_consent",
        "spp_vocabulary",
        "spp_programs",
        "spp_source_tracking",
    ],
    "data": [
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/config_data.xml",
        "data/fastapi_endpoint.xml",
        "data/api_path_data.xml",
        "data/filter_config_individual.xml",
        "data/filter_config_group.xml",
        "data/filter_config_program.xml",
        "data/filter_config_program_membership.xml",
        "wizards/show_secret_wizard_views.xml",
        "views/api_client_views.xml",
        "views/api_extension_views.xml",
        "views/api_path_views.xml",
        "views/consent_views.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "_post_init_hook",
    "summary": """
        OpenSPP API V2 - Standards-aligned, consent-respecting API for social protection data exchange.
    """,
    "description": """
OpenSPP API V2
==============

Standards-aligned, consent-respecting API for social protection data exchange.

Key Features
------------
- **External identifiers only** - Never exposes database IDs
- **Namespace URIs** - Uses globally unique URIs for all identifier types and vocabularies
- **Consent-based access control** - All data access requires explicit consent
- **Vocabulary system** - Uses spp.vocabulary for gender, relationships, etc.
- **Source tracking** - Tracks data provenance per ADR-008
- **OAuth 2.0** - Client credentials flow for authentication
- **Extensible** - Module-specific fields via extension mechanism

Design Principles
-----------------
- No database IDs exposed anywhere
- namespace_uri used for all identifier lookups
- gender_id used (not gender string)
- JWT secret from ir.config_parameter
- Source tracking on creates/updates
- Consent filtering on all reads

Architecture Decision Records
-----------------------------
- ADR-007: Namespace URIs for Identifiers
- ADR-008: Source Tracking and Provenance
- ADR-009: Terminology System

See docs/specs/api-v2/SPEC.md for full specification.
    """,
}
