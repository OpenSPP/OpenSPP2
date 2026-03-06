# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Case Management: CEL Rules",
    "summary": "CEL-based triage and assignment rules for case management",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "category": "OpenSPP/Monitoring",
    "depends": [
        "spp_security",
        "spp_case_base",
        "spp_cel_domain",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/case_triage_rule_views.xml",
        "views/case_assignment_rule_views.xml",
        "views/case_cel_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
