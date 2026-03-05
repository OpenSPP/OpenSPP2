# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Case Management: Session Integration",
    "summary": "Link sessions and training attendance to cases",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "category": "OpenSPP/Monitoring",
    "depends": [
        "spp_security",
        "spp_case_base",
        "spp_session_tracking",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/case_views.xml",
        "views/session_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
