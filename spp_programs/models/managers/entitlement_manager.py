# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class BaseEntitlementManager(models.AbstractModel):
    _inherit = "spp.base.program.entitlement.manager"

    id_type_id = fields.Many2one("spp.id.type", "ID Type to store in entitlements")
