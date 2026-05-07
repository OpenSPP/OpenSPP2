# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Irrigation",
    "category": "OpenSPP",
    "version": "19.0.2.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "depends": [
        "base",
        "spp_gis",
        "spp_security",
        "spp_registry",
        "spp_farmer_registry_vocabularies",
    ],
    "data": [
        "security/privileges.xml",
        "security/irrigation_security.xml",
        "security/ir.model.access.csv",
        "views/irrigation_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "Manages detailed irrigation assets by type, capacity, and unique identifiers, leveraging integrated GIS capabilities to map and display infrastructure locations and boundaries. The module models water distribution networks by defining and linking irrigation sources to destinations, providing critical data for strategic planning of resource allocation and infrastructure projects.",
}
