# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend API client scope to add studio resource."""

from odoo import fields, models


class ApiClientScope(models.Model):
    """Extend API client scope with studio resource."""

    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[
            ("studio", "Studio"),
        ],
        ondelete={"studio": "cascade"},
    )
