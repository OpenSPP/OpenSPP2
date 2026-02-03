# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import ValidationError

from odoo.addons.spp_programs.models.constants import STATE_APPROVED


class CashEntitlement(models.Model):
    _inherit = "spp.entitlement"

    id_number = fields.Char()

    def approve_entitlement(self):
        for rec in self:
            if rec.cycle_id.state != STATE_APPROVED:
                raise ValidationError("The cycle must be approved before approving entitlement")

        return super().approve_entitlement()
