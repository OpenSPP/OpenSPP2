# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extends API client scope to support GIS resources."""

from odoo import fields, models


class ApiClientScope(models.Model):
    """Extend API client scope to include GIS resources."""

    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[
            ("gis", "GIS"),
            ("statistics", "Statistics"),
        ],
        ondelete={"gis": "cascade", "statistics": "cascade"},
    )
