# pylint: disable=pointless-statement
{
    "name": "OpenSPP GRM: CEL Rules",
    "summary": "CEL-based routing and escalation rules for GRM tickets",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "category": "OpenSPP/Monitoring",
    "depends": [
        "spp_security",
        "spp_grm",
        "spp_cel_domain",
        "spp_case_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/grm_routing_rule_views.xml",
        "views/grm_escalation_rule_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": ["spp_grm", "spp_cel_domain"],
}
