# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Notary Evidence",
    "summary": "Notary evidence provider integration for CEL external variables",
    "category": "OpenSPP/Integration",
    "version": "19.0.1.0.0",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi"],
    "depends": [
        "mail",
        "spp_cel_domain",
        "spp_registry",
        "spp_api_v2",
        "spp_notary_client",
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/notary_claim_views.xml",
        "views/data_provider_views.xml",
        "wizards/catalog_sync_wizard_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
