# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Land Record",
    "category": "OpenSPP",
    "version": "19.0.1.3.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "depends": [
        "base",
        "spp_base_common",
        "spp_gis",
        "spp_registry",
        "spp_security",
        "spp_farmer_registry_vocabularies",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/land_record_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "The OpenSPP Land Record module digitizes and centralizes land parcel information, linking it to associated farms, ownership details, and lease agreements. It captures and displays geographical boundaries and coordinates on interactive maps, supporting land use classification and program planning.",
}
