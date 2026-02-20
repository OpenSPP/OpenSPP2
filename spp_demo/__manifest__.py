# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Demo",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123", "reichie020212", "emjay0921"],
    "summary": "Core demo module with data generator and sample data for OpenSPP",
    "depends": [
        "base",
        "spp_base_common",
        "spp_registry",
        "spp_vocabulary",
        "queue_job",
        "spp_security",
        "spp_area",
    ],
    "external_dependencies": {
        "python": ["faker"],
    },
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Data
        "data/users_data.xml",
        "data/ir_config_parameter_data.xml",
        "data/res_country.xml",
        # Views
        "views/res_config_view.xml",
        "views/demo_data_generator_view.xml",
        # Wizards
        "wizard/apps_wizard_view.xml",
        "wizard/demo_area_loader_view.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
