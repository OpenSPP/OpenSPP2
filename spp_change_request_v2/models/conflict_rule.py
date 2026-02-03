import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPCRConflictRule(models.Model):
    """Configuration for conflict detection rules per CR type."""

    _name = "spp.cr.conflict.rule"
    _description = "Change Request Conflict Rule"
    _order = "sequence, id"

    # ══════════════════════════════════════════════════════════════════════════
    # BASIC INFO
    # ══════════════════════════════════════════════════════════════════════════

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    cr_type_id = fields.Many2one(
        "spp.change.request.type",
        string="CR Type",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SCOPE CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    scope = fields.Selection(
        [
            ("registrant", "Same Registrant"),
            ("group", "Same Group/Household"),
            ("field", "Same Field Modified"),
            ("custom", "Custom Logic"),
        ],
        default="registrant",
        required=True,
        help=(
            "Registrant: Check CRs for same registrant only. "
            "Group: Check CRs for all members of same group. "
            "Field: Check only if same field being modified. "
            "Custom: Use Python hook for complex logic."
        ),
    )

    check_same_type_only = fields.Boolean(
        default=False,
        help="Only check for conflicts with CRs of the same type",
    )

    conflict_type_ids = fields.Many2many(
        "spp.change.request.type",
        "spp_cr_conflict_rule_type_rel",
        "rule_id",
        "type_id",
        string="Conflicting CR Types",
        help="If set, only check for conflicts with these CR types",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    action = fields.Selection(
        [
            ("block", "Block Submission"),
            ("warn", "Warning (Allow Override)"),
            ("log", "Log Only"),
        ],
        default="warn",
        required=True,
        help=(
            "Block: Prevent CR submission entirely. "
            "Warn: Show warning but allow override with permission. "
            "Log: Log conflict but don't notify user."
        ),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # STATE & TIME FILTERING
    # ══════════════════════════════════════════════════════════════════════════

    conflict_states = fields.Selection(
        [
            ("all_active", "All Active (Draft, Pending, Approved)"),
            ("pending_only", "Pending Only"),
            ("approved_only", "Approved Only (Not Applied)"),
            ("pending_approved", "Pending and Approved"),
        ],
        default="all_active",
        required=True,
        help="Which approval states to check for conflicts",
    )

    time_window_hours = fields.Integer(
        default=0,
        help="Only check CRs created within this time window (0 = no limit)",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FIELD-LEVEL CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    conflict_fields = fields.Char(
        help="Comma-separated list of detail fields to check for conflicts (for 'field' scope)",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # MESSAGING
    # ══════════════════════════════════════════════════════════════════════════

    conflict_message = fields.Text(
        translate=True,
        help="Custom message to show when conflict detected",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════════════════

    @api.constrains("scope", "conflict_fields")
    def _check_field_scope_config(self):
        for rec in self:
            if rec.scope == "field" and not rec.conflict_fields:
                raise ValidationError(_("Field scope requires conflict_fields to be specified."))

    # ══════════════════════════════════════════════════════════════════════════
    # METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def get_conflict_states_list(self):
        """Return list of approval states to check based on conflict_states field."""
        self.ensure_one()
        mapping = {
            "all_active": ["draft", "pending", "approved"],
            "pending_only": ["pending"],
            "approved_only": ["approved"],
            "pending_approved": ["pending", "approved"],
        }
        return mapping.get(self.conflict_states, ["draft", "pending", "approved"])

    def get_conflict_fields_list(self):
        """Return list of fields to check for field-level conflicts."""
        self.ensure_one()
        if not self.conflict_fields:
            return []
        return [f.strip() for f in self.conflict_fields.split(",") if f.strip()]

    def get_conflict_message(self, conflicting_crs):
        """Get the message to display for this conflict rule."""
        self.ensure_one()
        if self.conflict_message:
            return self.conflict_message

        # Default messages based on action
        cr_refs = ", ".join(conflicting_crs.mapped("name")[:5])
        if len(conflicting_crs) > 5:
            cr_refs += f" (+{len(conflicting_crs) - 5} more)"

        if self.action == "block":
            return (
                _(
                    "Cannot submit: conflicting change request(s) exist: %s. "
                    "Cancel or wait for them to be applied first."
                )
                % cr_refs
            )
        elif self.action == "warn":
            return (
                _("Warning: potential conflict with existing change request(s): %s. " "Review before proceeding.")
                % cr_refs
            )
        else:  # log
            return _("Conflict logged with change request(s): %s") % cr_refs
