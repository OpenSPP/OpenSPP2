# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Hazard & Emergency Management",
    "summary": "Provides hazard classification, incident recording, and impact assessment "
    "for emergency response. Links registrants to disaster events with geographic scope "
    "and severity tracking to enable targeted humanitarian assistance.",
    "category": "OpenSPP/Targeting",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212"],
    "depends": [
        "base",
        "spp_security",
        "spp_registry",
        "spp_area",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/impact_type_data.xml",
        "views/hazard_category_views.xml",
        "views/hazard_incident_views.xml",
        "views/hazard_impact_views.xml",
        "views/hazard_impact_type_views.xml",
        "views/registrant_views.xml",
        "views/menu.xml",
    ],
    "demo": [
        "demo/hazard_demo.xml",
    ],
    "assets": {},
    "application": True,
    "installable": True,
    "auto_install": False,
}
