# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ApiClientScope(models.Model):
    _inherit = "spp.api.client.scope"

    resource = fields.Selection(
        selection_add=[("change_request", "Change Request")],
        ondelete={"change_request": "cascade"},
    )
