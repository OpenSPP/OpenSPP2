# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Registry PII Display",
    "summary": "Mask registrant ID numbers with audited reveal",
    "category": "OpenSPP/Core",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_registry",
        "spp_pii_encryption",  # masked_char widget + reveal audit log
        "spp_data_classification",  # PII access groups gating the reveal
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "views/registry_id_views.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
