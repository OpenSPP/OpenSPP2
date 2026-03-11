# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Import Match",
    "summary": "OpenSPP Import Match enhances data import processes by intelligently matching incoming records against existing data, preventing duplication and ensuring registry integrity. It provides configurable matching logic and supports seamless updates to existing records during bulk data onboarding.",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.3.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": ["base", "spp_base_common", "base_import", "queue_job", "spp_security"],
    "data": [
        "data/queue_job_data.xml",
        "security/ir.model.access.csv",
        "views/import_match_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_import_match/static/src/import_match_selector/import_match_selector.js",
            "spp_import_match/static/src/import_match_selector/import_match_selector.xml",
        ],
    },
    "demo": [],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
