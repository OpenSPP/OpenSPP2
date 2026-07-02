# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP MIS Demo V2",
    "summary": "Demo Generator V2 for SP-MIS programs with fixed stories and volume generation",
    "category": "OpenSPP",
    "version": "19.0.2.0.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        # SP-MIS Starter Bundle (includes registry, programs, API, DCI, CR, CEL, etc.)
        "spp_starter_sp_mis",
        # Advanced CR Types (Add/Remove Member, Exit, Split, Merge, etc.)
        "spp_cr_types_advanced",
        # Demo Infrastructure
        "spp_demo",
        # GIS Reports for geographic visualization
        "spp_gis_report",
        # Registrant GPS coordinates for QGIS plugin demo
        "spp_registrant_gis",
        # Indicators and analytics for demo indicators
        "spp_indicator",
        "spp_analytics",
        "spp_studio",
        # GIS API (used by QGIS plugin and PRISM frontend)
        "spp_api_v2_gis",
        # QR Credentials (Claim 169)
        "spp_claim_169",
        # Banking (for bank account demo data)
        "spp_banking",
        # Demo-specific extensions
    ],
    "external_dependencies": {"python": ["requests"]},
    "post_init_hook": "post_init_hook",
    "data": [
        "security/ir.model.access.csv",
        "data/vocabulary_group_membership_type.xml",
        "data/demo_currencies.xml",
        "data/demo_constants.xml",
        "data/demo_personas.xml",
        "data/demo_users.xml",
        "data/approval_definitions.xml",
        "data/demo_programs.xml",
        "data/event_types.xml",
        "data/change_request_types.xml",
        "data/demo_change_requests_ux.xml",
        "data/demo_gis_reports.xml",
        "data/demo_statistics.xml",
        "data/demo_api_client.xml",
        "views/mis_demo_wizard_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
