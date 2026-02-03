# pylint: disable=pointless-statement
# Copyright 2021 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Endpoint route handler",
    "category": "Hidden",
    "summary": """Provide mixin and tool to generate custom endpoints on the fly.""",
    "version": "19.0.1.1.0",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "author": "Camptocamp,Odoo Community Association (OCA)",
    "maintainers": ["simahawk"],
    "website": "https://github.com/OpenSPP/openspp-modules",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "post_init_hook": "post_init_hook",
}
