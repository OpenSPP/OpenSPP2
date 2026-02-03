# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Starter: SP-MIS",
    "summary": "Complete SP-MIS bundle with Social Registry, Programs, and Service Points",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        # Social Registry Foundation
        "spp_starter_social_registry",
        # Program Management
        "spp_programs",  # Note: includes spp_service_points as transitive dependency
        "spp_approval",
        "spp_event_data",
        # Note: spp_api_v2_cycles auto-installs with spp_api_v2 + spp_programs
    ],
    "data": [
        "data/config_parameters.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_starter_sp_mis/static/src/js/registry_restriction.js",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Starter: SP-MIS
=======================

A comprehensive bundle for Social Protection Management Information System
deployments. Extends the Social Registry with program management capabilities.

Included Capabilities
---------------------
Everything in ``spp_starter_social_registry`` plus:

- **Program Management**: Define programs with eligibility criteria
- **Enrollment**: Manage beneficiary enrollment and membership
- **Cycles**: Payment and distribution cycle management
- **Event Data**: Audit trail for program activities
- **Service Points**: Manage distribution and service delivery locations
- **Approval Workflows**: Multi-level approval for sensitive operations

Use Cases
---------
- Cash Transfer Programs
- Conditional Cash Transfers
- Social Assistance Programs
- Food Distribution Programs
- In-Kind Transfer Programs

For demo data and sample programs, also install ``spp_mis_demo_v2``.
    """,
}
