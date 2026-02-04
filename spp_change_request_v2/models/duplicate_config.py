import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPCRDuplicateConfig(models.Model):
    """Configuration for duplicate detection per CR type."""

    _name = "spp.cr.duplicate.config"
    _description = "Change Request Duplicate Detection Configuration"

    # ══════════════════════════════════════════════════════════════════════════
    # BASIC INFO
    # ══════════════════════════════════════════════════════════════════════════

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )
    active = fields.Boolean(default=True)

    cr_type_id = fields.Many2one(
        "spp.change.request.type",
        string="CR Type",
        required=True,
        ondelete="cascade",
        index=True,
    )

    @api.depends("cr_type_id.name")
    def _compute_name(self):
        for rec in self:
            if rec.cr_type_id:
                rec.name = _("Duplicate Config: %s") % rec.cr_type_id.name
            else:
                rec.name = _("Duplicate Config")

    # ══════════════════════════════════════════════════════════════════════════
    # TIME WINDOW
    # ══════════════════════════════════════════════════════════════════════════

    time_window_hours = fields.Integer(
        default=48,
        help="Only check for duplicates within this time window (hours)",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SIMILARITY CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    similarity_threshold = fields.Float(
        default=90.0,
        help="Minimum similarity percentage (0-100) to consider as duplicate",
    )

    check_fields = fields.Char(
        help=("Comma-separated list of detail fields to compare. If empty, compares all fields."),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # AUTO-MERGE CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    auto_merge_enabled = fields.Boolean(
        default=False,
        help="Automatically merge exact duplicates (100% similarity) in draft state",
    )

    auto_merge_states = fields.Selection(
        [
            ("draft_only", "Draft Only"),
            ("draft_pending", "Draft and Pending"),
        ],
        default="draft_only",
        help="Which states allow auto-merging",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════════════════

    @api.constrains("similarity_threshold")
    def _check_similarity_threshold(self):
        for rec in self:
            if rec.similarity_threshold < 0 or rec.similarity_threshold > 100:
                raise ValidationError(_("Similarity threshold must be between 0 and 100."))

    @api.constrains("time_window_hours")
    def _check_time_window(self):
        for rec in self:
            if rec.time_window_hours < 0:
                raise ValidationError(_("Time window must be non-negative."))

    @api.constrains("cr_type_id")
    def _check_cr_type_unique(self):
        for rec in self:
            if rec.cr_type_id:
                existing = self.search(
                    [
                        ("cr_type_id", "=", rec.cr_type_id.id),
                        ("id", "!=", rec.id),
                    ]
                )
                if existing:
                    raise ValidationError(_("Only one duplicate configuration per CR type is allowed."))

    # ══════════════════════════════════════════════════════════════════════════
    # METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def get_check_fields_list(self):
        """Return list of fields to compare for duplicate detection."""
        self.ensure_one()
        if not self.check_fields:
            return []
        return [f.strip() for f in self.check_fields.split(",") if f.strip()]

    def get_auto_merge_states_list(self):
        """Return list of states that allow auto-merging."""
        self.ensure_one()
        if not self.auto_merge_enabled:
            return []
        if self.auto_merge_states == "draft_only":
            return ["draft"]
        return ["draft", "pending"]
