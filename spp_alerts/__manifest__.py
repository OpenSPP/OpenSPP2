# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Alerts",
    "summary": "Generic alert engine for threshold monitoring, expiry tracking, "
    "and deadline management across OpenSPP modules.",
    "category": "OpenSPP/Infrastructure",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "base",
        "mail",
        "spp_security",
        "spp_vocabulary",
    ],
    "data": [
        # Security (must be first)
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        # Data
        "data/ir_sequence.xml",
        "data/vocabulary_namespaces.xml",
        "data/vocabulary_codes.xml",
        # Views
        "views/alert_views.xml",
        "views/alert_rule_views.xml",
        "views/menus.xml",
    ],
    "assets": {},
    "application": False,
    "installable": True,
    "auto_install": False,
}
