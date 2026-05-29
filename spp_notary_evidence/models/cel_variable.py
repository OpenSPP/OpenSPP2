# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CELVariable(models.Model):
    _inherit = "spp.cel.variable"

    notary_claim_id = fields.Many2one(
        comodel_name="spp.notary.claim",
        string="Notary Claim",
        ondelete="set null",
    )
    notary_value_path = fields.Char(
        string="Notary Value Path",
        default="value",
    )
