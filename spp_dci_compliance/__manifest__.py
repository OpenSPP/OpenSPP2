# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP DCI Compliance Tests",
    "summary": "DCI compliance validation test suite (test-only, disabled by default)",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "job_worker",
        "spp_dci",
        "spp_dci_server",
        "spp_dci_server_social",
        "spp_registry",
        "web",
    ],
    "external_dependencies": {
        "python": ["jsonschema"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/test_senders.xml",
        "data/test_identifiers.xml",
        "data/test_individuals.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_dci_compliance/static/src/components/**/*",
        ],
    },
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": False,
}
