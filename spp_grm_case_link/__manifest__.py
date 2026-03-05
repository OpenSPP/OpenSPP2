# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP GRM Case Link",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Links GRM tickets with Case Management cases for escalation",
    "author": "OpenSPP",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "spp_grm",
        "spp_case_base",
    ],
    "data": [
        # Security
        "security/grm_case_link_security.xml",
        "security/ir.model.access.csv",
        # Views
        "views/grm_ticket_views.xml",
        "views/case_views.xml",
        "views/escalate_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": True,
}
