# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP Scoring Programs Bridge",
    "category": "OpenSPP/Targeting",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "development_status": "Beta",
    "summary": "Integrates scoring with program eligibility and entitlements",
    "description": """
OpenSPP Scoring Programs Bridge
===============================

Links the scoring framework with program management for:
- Score-based eligibility criteria
- Automatic scoring during enrollment
- Classification-based benefit tiers

This module auto-installs when both spp_scoring and spp_programs are installed.
    """,
    "depends": [
        "spp_scoring",
        "spp_programs",
    ],
    "data": [
        # Note: No ACL entries needed - this module only extends existing models
        # (spp.program, spp.program.membership, spp.scoring.model) which have
        # their own ACLs defined in their respective modules.
        "views/scoring_model_views.xml",
        "views/program_views.xml",
    ],
    "assets": {},
    "application": False,
    "installable": True,
    "auto_install": True,
}
