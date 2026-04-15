# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extends res.partner with scoring result count and actions."""

from odoo import api, fields, models


class ResPartner(models.Model):
    """Add scoring smart button to registrant form."""

    _inherit = "res.partner"

    scoring_result_ids = fields.One2many(
        "spp.scoring.result",
        "registrant_id",
        string="Scoring Results",
    )
    scoring_result_count = fields.Integer(
        string="# Scores",
        compute="_compute_scoring_result_count",
    )

    @api.depends("scoring_result_ids")
    def _compute_scoring_result_count(self):
        for partner in self:
            partner.scoring_result_count = len(partner.scoring_result_ids)

    def action_view_scoring_results(self):
        """Open scoring results for this registrant."""
        self.ensure_one()
        return {
            "name": self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.scoring.result",
            "view_mode": "list,form",
            "domain": [("registrant_id", "=", self.id)],
            "context": {"default_registrant_id": self.id},
        }

    def action_score_registrant(self):
        """Open the batch scoring wizard pre-filled for this registrant."""
        self.ensure_one()
        return {
            "name": "Score Registrant",
            "type": "ir.actions.act_window",
            "res_model": "spp.batch.scoring.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_registrant_ids": self.ids,
                "default_domain": f"[('id', '=', {self.id})]",
            },
        }
