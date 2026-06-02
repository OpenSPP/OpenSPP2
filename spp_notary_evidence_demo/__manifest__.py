# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Notary Evidence Demo",
    "summary": "Demo Registry Notary providers, personas, and programs for the registry-lab stack",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.2",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi"],
    "depends": [
        "spp_notary_evidence",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/demo_run_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
