# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ApiClientScope(models.Model):
    """Extend API Client Scope to add product resource type."""

    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[("product", "Product")],
        ondelete={"product": "cascade"},
    )
