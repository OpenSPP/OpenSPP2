# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Program Geofence",
    "summary": "Geofence-based geographic targeting for programs using spatial queries.",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_programs",
        "spp_gis",
        "spp_registrant_gis",
        "spp_area",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/geofence_view.xml",
        "views/eligibility_manager_view.xml",
        "views/program_view.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
