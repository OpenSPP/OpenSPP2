# pylint: disable=pointless-statement
{
    "name": "OpenSPP GRM Registry Integration",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Monitoring",
    "summary": "Link GRM tickets to OpenSPP registry (registrants)",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "spp_grm",
        "spp_registry",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/grm_ticket_views.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
