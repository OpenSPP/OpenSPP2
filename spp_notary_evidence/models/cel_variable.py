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
    effective_purpose_url = fields.Char(
        string="Effective Purpose URL",
        compute="_compute_effective_purpose_url",
        help="Purpose URL used for Notary evaluation before evaluation-context overrides.",
    )

    def _compute_effective_purpose_url(self):
        for variable in self:
            claim = variable.notary_claim_id
            variable.effective_purpose_url = (
                claim.default_purpose_url or claim.provider_id.notary_default_purpose_url if claim else False
            )
