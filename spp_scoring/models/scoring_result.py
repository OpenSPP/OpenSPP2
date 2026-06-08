import json
import logging

from odoo import api, fields, models
from odoo.tools.sql import create_index

_logger = logging.getLogger(__name__)


class SppScoringResult(models.Model):
    """Stores calculated scores for registrants."""

    _name = "spp.scoring.result"
    _description = "Scoring Result"
    _inherit = ["mail.thread"]
    _order = "calculation_date desc, id desc"

    display_name = fields.Char(compute="_compute_display_name")

    # Core relationships
    registrant_id = fields.Many2one(
        comodel_name="res.partner",
        string="Registrant",
        required=True,
        ondelete="cascade",
        domain="[('is_registrant', '=', True)]",
        index=True,
    )
    model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        required=True,
        ondelete="restrict",
        index=True,
    )

    # Score data
    score = fields.Float(
        string="Score",
        required=True,
        tracking=True,
        help="Calculated total score",
    )
    classification_code = fields.Char(
        string="Classification Code",
        tracking=True,
        help="Machine-readable classification",
    )
    classification_label = fields.Char(
        string="Classification",
        tracking=True,
        help="Human-readable classification",
    )
    classification_color = fields.Selection(
        selection=[
            ("red", "Red"),
            ("orange", "Orange"),
            ("yellow", "Yellow"),
            ("green", "Green"),
            ("blue", "Blue"),
            ("purple", "Purple"),
            ("gray", "Gray"),
        ],
        string="Classification Color",
    )

    # Metadata
    calculation_date = fields.Datetime(
        string="Calculation Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    calculated_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Calculated By",
        default=lambda self: self.env.user,
        help="User who triggered the calculation, or system for batch",
    )
    calculation_mode = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("batch", "Batch"),
            ("automatic", "Automatic"),
        ],
        string="Calculation Mode",
        default="manual",
    )

    # Input/output snapshots (JSON)
    inputs_snapshot = fields.Text(
        string="Inputs Snapshot",
        help="JSON blob of field values at calculation time",
    )
    breakdown_json = fields.Text(
        string="Breakdown JSON",
        help="JSON structure showing per-indicator contributions",
    )

    # Breakdown details (relational)
    detail_ids = fields.One2many(
        comodel_name="spp.scoring.result.detail",
        inverse_name="result_id",
        string="Score Breakdown",
    )

    # Status and errors
    is_complete = fields.Boolean(
        string="Complete",
        default=True,
        help="False if calculation had errors or missing data",
    )
    error_messages = fields.Text(
        string="Error Messages",
        help="Any errors or warnings from calculation",
    )

    # Model version tracking
    model_version = fields.Char(
        string="Model Version",
        help="Version of the scoring model used",
    )
    model_code = fields.Char(
        string="Model Code",
        related="model_id.code",
        store=True,
    )

    # Registrant info (for display)
    registrant_name = fields.Char(
        related="registrant_id.name",
        string="Registrant Name",
        store=True,
    )

    @api.depends("registrant_id", "model_id", "score", "classification_label")
    def _compute_display_name(self):
        for record in self:
            parts = [
                record.registrant_id.name or "",
                record.model_id.code or "",
                f"{record.score:.2f}",
            ]
            if record.classification_label:
                parts.append(record.classification_label)
            record.display_name = " - ".join(parts)

    def _auto_init(self):
        """Create performance indexes for large-scale operations."""
        res = super()._auto_init()

        # Compound index for get_latest_score() lookups
        # This is critical for performance with millions of results
        create_index(
            self.env.cr,
            "spp_scoring_result_registrant_model_date_idx",
            self._table,
            ["registrant_id", "model_id", "calculation_date DESC"],
        )

        # Index for filtering by classification (program eligibility)
        create_index(
            self.env.cr,
            "spp_scoring_result_classification_idx",
            self._table,
            ["model_id", "classification_code"],
        )

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Store model version at creation time
            if vals.get("model_id") and not vals.get("model_version"):
                model = self.env["spp.scoring.model"].browse(vals["model_id"])
                vals["model_version"] = model.version
        return super().create(vals_list)

    def get_breakdown(self):
        """Return the breakdown as a parsed dict."""
        self.ensure_one()
        if self.breakdown_json:
            try:
                return json.loads(self.breakdown_json)
            except json.JSONDecodeError:
                return []
        return []

    def get_inputs(self):
        """Return the inputs snapshot as a parsed dict."""
        self.ensure_one()
        if self.inputs_snapshot:
            try:
                return json.loads(self.inputs_snapshot)
            except json.JSONDecodeError:
                return {}
        return {}

    def action_recalculate(self):
        """Recalculate the score using the current model."""
        engine = self.env["spp.scoring.engine"]
        for record in self:
            engine.calculate_score(
                record.registrant_id,
                record.model_id,
                mode="manual",
            )
        return True

    def action_view_registrant(self):
        """Open the registrant form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.registrant_id.name,
            "res_model": "res.partner",
            "res_id": self.registrant_id.id,
            "view_mode": "form",
        }

    def get_age_in_days(self):
        """Return the age of this score in days."""
        self.ensure_one()
        if not self.calculation_date:
            return 0
        delta = fields.Datetime.now() - self.calculation_date
        return delta.days

    @api.model
    def get_latest_score(self, registrant, model, max_age_days=None):
        """Get the most recent score for a registrant/model — including
        incomplete rows. The latest attempt reflects the registrant's
        current scoreability: if their data became invalid after a
        previously successful score, the most recent (incomplete) row
        is the truth, not the stale complete one. Callers that need to
        gate behaviour on success must check ``result.is_complete``.
        See OP#838.
        """
        domain = [
            ("registrant_id", "=", registrant.id),
            ("model_id", "=", model.id),
        ]
        result = self.search(domain, limit=1, order="calculation_date desc, id desc")

        if result and max_age_days:
            if result.get_age_in_days() > max_age_days:
                return None

        return result
