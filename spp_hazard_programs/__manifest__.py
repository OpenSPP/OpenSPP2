# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Hazard Programs Integration",
    "summary": "Links hazard impacts to program eligibility and entitlements. "
    "Enables emergency programs to use hazard data for targeting and benefit calculation.",
    "category": "OpenSPP/Targeting",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_hazard",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/program_views.xml",
        "views/incident_views.xml",
    ],
    "demo": [],
    "assets": {},
    "application": False,
    "installable": True,
    "auto_install": True,
}
