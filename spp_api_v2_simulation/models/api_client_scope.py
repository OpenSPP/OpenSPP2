# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extends API client scope to support simulation and aggregation resources."""

from odoo import fields, models


class ApiClientScope(models.Model):
    """Extend API client scope to include simulation and aggregation resources."""

    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[
            ("simulation", "Simulation"),
            ("aggregation", "Aggregation"),
        ],
        ondelete={
            "simulation": "cascade",
            "aggregation": "cascade",
        },
    )

    action = fields.Selection(
        selection_add=[
            ("execute", "Execute"),
            ("convert", "Convert"),
        ],
        ondelete={"execute": "cascade", "convert": "cascade"},
    )
