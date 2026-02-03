import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LogicVersion(models.Model):
    """Version history for logic rules.

    Each time a logic definition is published, a snapshot is created
    to maintain a complete audit trail of all changes over time.
    """

    _name = "spp.studio.version"
    _description = "Logic Version History"
    _order = "logic_id, version desc"

    logic_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Logic",
        required=True,
        ondelete="cascade",
        index=True,
        help="The logic definition this version belongs to",
    )
    version = fields.Integer(
        string="Version Number",
        required=True,
        help="Sequential version number (1, 2, 3...)",
    )
    cel_expression = fields.Text(
        string="CEL Expression",
        help="The compiled CEL expression that was published",
    )
    published_date = fields.Datetime(
        string="Published Date",
        help="When this version was published",
    )
    published_by = fields.Many2one(
        comodel_name="res.users",
        string="Published By",
        ondelete="set null",
        help="User who published this version",
    )
    change_summary = fields.Text(
        string="Change Summary",
        help="Description of what changed in this version",
    )
    state = fields.Selection(
        selection=[
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        string="State",
        default="published",
        required=True,
        help="Current state of this version",
    )

    @api.constrains("logic_id", "version")
    def _check_version_unique(self):
        """Ensure version number is unique per logic definition."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("logic_id", "=", rec.logic_id.id),
                    ("version", "=", rec.version),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("Version number %s already exists for this logic.") % rec.version)

    @api.constrains("version")
    def _check_version_positive(self):
        """Ensure version number is positive."""
        for rec in self:
            if rec.version <= 0:
                raise ValidationError(_("Version number must be positive."))

    def action_view_version(self):
        """View this version's details."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Version %s") % self.version,
            "res_model": "spp.studio.version",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_restore_version(self):
        """Restore this version to the main logic."""
        self.ensure_one()
        logic = self.logic_id
        if logic:
            restore_vals = {
                "cel_expression": self.cel_expression,
                "compiled_expression": self.cel_expression,  # Use cel_expression as compiled
                "state": "draft",
            }
            logic.write(restore_vals)
            _logger.info(
                "Restored version %s to logic %s",
                self.version,
                logic.name,
            )
        return {"type": "ir.actions.act_window_close"}
