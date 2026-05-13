# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP Event Data",
    "category": "OpenSPP",
    "version": "19.0.2.0.1",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
    "maintainers": [
        "jeremi",
        "gonzalesedwin1123",
        "emjay0921",
    ],
    "depends": [
        "base",
        "mail",
        "spp_registry",
        "spp_base_common",
        "spp_security",
        "spp_approval",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/event_type_views.xml",
        "views/event_data_view.xml",
        "views/registrant_view.xml",
        # Wizards
        "wizard/create_event_wizard.xml",
        # Data
        "data/ir_cron.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "summary": "Records and tracks events related to individual and group registrants from surveys, field visits, and external systems like ODK and KoBoToolbox.",
}
