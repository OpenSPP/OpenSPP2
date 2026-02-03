# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Source Tracking",
    "summary": "Track data provenance and source information for registrants",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["OpenSPP"],
    "depends": ["base", "spp_security", "spp_registry", "spp_programs"],
    "data": [
        "security/ir.model.access.csv",
        "views/merge_provenance_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
