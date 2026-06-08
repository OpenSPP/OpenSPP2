# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP DCI Client - Social Registry",
    "summary": "DCI client for querying external Social Registries",
    "version": "19.0.1.0.1",
    "category": "OpenSPP",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "depends": [
        "fastapi",
        "spp_dci_client",
        "spp_registry",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/sr_sender_views.xml",
        "views/sr_record_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "application": False,
}
