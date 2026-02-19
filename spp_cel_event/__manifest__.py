# pylint: disable=pointless-statement
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

{
    "name": "OpenSPP CEL Event Data Integration",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_cel_domain",
        "spp_event_data",
        "spp_studio",  # For CEL variable form extensions
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/cel_variable_event_agg_views.xml",
        # Note: cel_profiles.yaml is loaded programmatically by spp.cel.registry
        # (not listed here because Odoo can't load YAML files directly)
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": True,
    "post_init_hook": "post_init_hook",
    "summary": "Integrate event data with CEL expressions for eligibility and entitlement rules",
}
