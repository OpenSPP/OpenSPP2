# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement
{
    "name": "OpenSPP Child Benefit",
    "category": "OpenSPP/Programs",
    "version": "19.0.1.1.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "summary": "Birth-order based child benefit: sibling ranking, scheduled monthly entitlements, payment file export, and portal monitoring.",
    "depends": [
        "portal",
        "spp_banking",
        "spp_programs",
        "spp_registry",
        "spp_security",
        "spp_vocabulary",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/membership_type_data.xml",
        "data/ir_sequence_data.xml",
        "views/individual_views.xml",
        "views/entitlement_schedule_views.xml",
        "views/portal_templates.xml",
        "views/create_program_wizard_views.xml",
        "views/payment_batch_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "spp_child_benefit/static/src/css/portal.css",
        ],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
}
