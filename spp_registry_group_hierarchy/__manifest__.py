# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Registry Group Hierarchy",
    "summary": "The module introduces hierarchical relationships among OpenSPP registry groups, enabling the creation of nested structures where groups can contain both individuals and other sub-groups. It extends g2p_registry_group and g2p_registry_membership modules.",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_security",
        "base",
        "spp_registry",
        "spp_vocabulary",
    ],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "views/group_membership_views.xml",
        "views/group_views.xml",
        "views/vocabulary_code_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
