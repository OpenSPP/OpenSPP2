# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ApiClientScope(models.Model):
    """Extend API Client Scope to add service_point resource type."""

    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[("service_point", "Service Point")],
        ondelete={"service_point": "cascade"},
    )
