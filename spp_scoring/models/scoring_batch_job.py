import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SppScoringBatchJob(models.Model):
    """Tracks batch scoring job progress for async processing."""

    _name = "spp.scoring.batch.job"
    _description = "Batch Scoring Job"
    _order = "create_date desc"

    model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Completed"),
            ("failed", "Failed"),
        ],
        string="State",
        default="pending",
        required=True,
        index=True,
    )
    total_count = fields.Integer(
        string="Total Registrants",
        required=True,
    )
    successful_count = fields.Integer(
        string="Successful",
        default=0,
    )
    failed_count = fields.Integer(
        string="Failed",
        default=0,
    )
    completed_date = fields.Datetime(
        string="Completed Date",
    )
    created_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Created By",
        default=lambda self: self.env.user,
    )

    def name_get(self):
        result = []
        for record in self:
            name = _("Batch %s - %s") % (record.id, record.model_id.code or "")
            result.append((record.id, name))
        return result

    def action_view_results(self):
        """View scoring results created by this batch."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Results"),
            "res_model": "spp.scoring.result",
            "view_mode": "list,form",
            "domain": [
                ("model_id", "=", self.model_id.id),
                ("calculation_mode", "=", "batch"),
                ("create_date", ">=", self.create_date),
            ],
        }
