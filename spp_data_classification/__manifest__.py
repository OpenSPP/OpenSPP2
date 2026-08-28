# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Data Classification",
    "summary": "Data sensitivity classification and PII protection for OpenSPP",
    "category": "OpenSPP/Configuration",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "base",
        "spp_security",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "data/classification_levels.xml",
        "data/detection_patterns.xml",
        "views/field_classification_views.xml",
        "views/classification_level_views.xml",
        "views/classification_pattern_views.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
