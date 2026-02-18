# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


{
    "name": "OpenSPP Area Management",
    "summary": "Establishes direct associations between OpenSPP registrants, beneficiary groups, and their corresponding geographical administrative areas. It validates registrant-area linkages against official area types, ensuring data integrity and enabling targeted program delivery and analysis.",
    "category": "OpenSPP/Core",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "depends": [
        "base",
        "spp_base_common",
        "spp_user_roles",
        "spp_registry",
        "job_worker",
        "spp_security",
    ],
    "external_dependencies": {
        "python": [
            "openpyxl",
        ]
    },
    "data": [
        "data/area_type_data.xml",
        "data/area_tag_data.xml",
        "data/queue_limit_data.xml",
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "wizard/area_import_language_wizard_views.xml",
        "views/area_base.xml",
        "views/area_tag.xml",
        "views/area_type_base.xml",
        "views/area_import_views.xml",
        "views/area_type.xml",
        "views/individual_views.xml",
        "views/group_views.xml",
        "views/role.xml",
        "views/user.xml",
        "views/area.xml",
        "views/area_import.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
