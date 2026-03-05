# pylint: disable=pointless-statement

{
    "name": "OpenSPP GRM Programs Integration",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Link GRM tickets to OpenSPP programs, entitlements, and payments",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "spp_grm",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/grm_ticket_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
