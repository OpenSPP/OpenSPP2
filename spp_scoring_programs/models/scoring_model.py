from odoo import fields, models


class SppScoringModel(models.Model):
    """Extends scoring model with program relationships."""

    _inherit = "spp.scoring.model"

    program_ids = fields.Many2many(
        comodel_name="spp.program",
        relation="spp_scoring_model_program_rel",
        column1="scoring_model_id",
        column2="program_id",
        string="Programs",
        help="Programs that use this scoring model for eligibility",
    )
    program_count = fields.Integer(
        string="Program Count",
        compute="_compute_program_count",
    )

    def _compute_program_count(self):
        for record in self:
            record.program_count = len(record.program_ids)

    def action_view_programs(self):
        """View programs using this scoring model."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Programs",
            "res_model": "spp.program",
            "view_mode": "list,form",
            "domain": [("id", "in", self.program_ids.ids)],
        }
