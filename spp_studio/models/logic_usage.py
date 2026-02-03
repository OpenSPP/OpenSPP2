import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LogicUsage(models.Model):
    """Track where logic rules are being used.

    Records all places where a logic definition is referenced,
    enabling impact analysis and preventing deletion of in-use logic.
    """

    _name = "spp.studio.usage"
    _description = "Logic Usage Tracking"
    _order = "logic_id, res_model, res_id"

    logic_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Logic",
        required=True,
        ondelete="cascade",
        index=True,
        help="The logic definition being used",
    )
    res_model = fields.Char(
        string="Resource Model",
        required=True,
        index=True,
        help="Technical name of the model using this logic (e.g., 'spp.program')",
    )
    res_id = fields.Integer(
        string="Resource ID",
        required=True,
        index=True,
        help="Database ID of the record using this logic",
    )
    res_name = fields.Char(
        string="Resource Name",
        compute="_compute_res_name",
        store=True,
        help="Display name of the record using this logic",
    )
    usage_type = fields.Selection(
        selection=[
            ("filter", "Filter"),
            ("formula", "Formula"),
            ("scoring", "Scoring"),
            ("other", "Other"),
        ],
        string="Usage Type",
        default="other",
        help="How this logic is being used in the target record",
    )

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        """Compute the display name of the referenced record."""
        for record in self:
            if record.res_model and record.res_id:
                try:
                    target_model = self.env[record.res_model]
                    target_record = target_model.browse(record.res_id)
                    if target_record.exists():
                        record.res_name = target_record.display_name
                    else:
                        record.res_name = f"Deleted ({record.res_model} #{record.res_id})"
                except Exception as e:
                    _logger.warning(
                        "Failed to compute res_name for usage %s: %s",
                        record.id,
                        str(e),
                    )
                    record.res_name = f"{record.res_model} #{record.res_id}"
            else:
                record.res_name = False

    @api.constrains("logic_id", "res_model", "res_id")
    def _check_usage_unique(self):
        """Ensure usage record is unique per resource."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("logic_id", "=", rec.logic_id.id),
                    ("res_model", "=", rec.res_model),
                    ("res_id", "=", rec.res_id),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("Logic usage record already exists for this resource."))

    def action_open_record(self):
        """Open the record that uses this logic."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "name": _("Record"),
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
