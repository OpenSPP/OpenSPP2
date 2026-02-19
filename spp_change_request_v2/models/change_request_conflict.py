import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPChangeRequestConflict(models.Model):
    """Extension of spp.change.request with conflict detection capabilities."""

    _name = "spp.change.request"
    _inherit = ["spp.change.request", "spp.cr.conflict.mixin"]

    # ══════════════════════════════════════════════════════════════════════════
    # OVERRIDE CRUD TO INTEGRATE CONFLICT DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        """Run conflict detection on creation."""
        records = super().create(vals_list)

        for record in records:
            # Run conflict checks if enabled for this CR type
            if record.request_type_id and (
                record.request_type_id.enable_conflict_detection or record.request_type_id.enable_duplicate_detection
            ):
                try:
                    record._run_conflict_checks()
                except Exception as e:
                    # Log at error level and notify via message
                    _logger.exception("Conflict detection failed for CR %s", record.name)
                    # Post message so user is aware of the issue
                    record.message_post(
                        body=_("Warning: Conflict detection failed: %s. Manual review recommended.") % str(e),
                        message_type="notification",
                    )

        return records

    def write(self, vals):
        """Re-run conflict detection if relevant fields change."""
        result = super().write(vals)

        # Re-check conflicts if registrant or type changed
        if "registrant_id" in vals or "request_type_id" in vals:
            for record in self:
                if (
                    record.request_type_id
                    and record.approval_state == "draft"
                    and (
                        record.request_type_id.enable_conflict_detection
                        or record.request_type_id.enable_duplicate_detection
                    )
                ):
                    try:
                        record._run_conflict_checks()
                    except Exception as e:
                        # Log at error level and notify via message
                        _logger.exception("Conflict re-check failed for CR %s", record.name)
                        record.message_post(
                            body=_("Warning: Conflict re-check failed: %s. Manual review recommended.") % str(e),
                            message_type="notification",
                        )

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # OVERRIDE APPROVAL HOOKS
    # ══════════════════════════════════════════════════════════════════════════

    def _on_submit(self):
        """Check for blocking conflicts before submission."""
        # Run conflict check first
        for record in self:
            if record.request_type_id and record.request_type_id.enable_conflict_detection:
                result = record._run_conflict_checks()

                if result["needs_override"]:
                    # Check if already overridden
                    if record.conflict_status != "overridden":
                        raise ValidationError(
                            _("Cannot submit: blocking conflicts detected.\n\n%s") % "\n".join(result["messages"])
                        )

                # Log warnings even if proceeding
                if result["messages"] and result["can_proceed"]:
                    _logger.info(
                        "CR %s submitted with warnings: %s",
                        record.name,
                        "; ".join(result["messages"]),
                    )

        # Continue with normal submission
        super()._on_submit()

    def _on_approve(self):
        """Re-check conflicts at approval time."""
        for record in self:
            if record.request_type_id and record.request_type_id.enable_conflict_detection:
                # Re-run conflict check with fresh data
                result = record._run_conflict_checks()

                # If new blocking conflicts appeared since submission
                if result["needs_override"] and record.conflict_status != "overridden":
                    raise ValidationError(
                        _("Cannot approve: new conflicts detected since submission.\n\n%s")
                        % "\n".join(result["messages"])
                    )

        super()._on_approve()

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT-AWARE HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def get_conflict_summary(self):
        """Get a summary of conflicts for display."""
        self.ensure_one()

        summary = {
            "has_conflicts": self.conflict_count > 0,
            "has_duplicates": self.duplicate_count > 0,
            "conflict_status": self.conflict_status,
            "duplicate_status": self.duplicate_status,
            "is_blocked": self.conflict_status == "blocked",
            "is_overridden": self.conflict_status == "overridden",
            "conflict_count": self.conflict_count,
            "duplicate_count": self.duplicate_count,
            "similarity_score": self.duplicate_similarity_score,
        }

        if self.conflict_messages:
            summary["messages"] = self.conflict_messages.split("\n")
        else:
            summary["messages"] = []

        return summary

    def can_be_submitted(self):
        """Check if this CR can be submitted (considering conflicts)."""
        self.ensure_one()

        if self.approval_state != "draft":
            return False, _("CR is not in draft state.")

        if self.conflict_status == "blocked":
            if not self.env.user.has_group("spp_change_request_v2.group_cr_conflict_approver"):
                return False, _("Blocking conflicts exist and cannot be overridden.")

        return True, ""

    def action_quick_cancel_this(self):
        """Quick action to cancel this CR due to conflict.

        This provides a one-click solution for users who want to cancel
        their request when they see it conflicts with another one.
        """
        self.ensure_one()

        # Pre-translate messages before any deletions (avoid cursor invalidation issues)
        title_cancelled = _("Request Cancelled")
        message_cancelled = _("Your change request has been cancelled.")
        title_list = _("Change Requests")
        title_cannot = _("Cannot Cancel")
        message_cannot = _("This request cannot be cancelled in its current state.")

        if self.approval_state == "pending":
            self._do_reject(_("Cancelled by user due to conflict"))
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": title_cancelled,
                    "message": message_cancelled,
                    "type": "info",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        elif self.approval_state == "draft":
            # Delete detail record first to avoid FK violation
            detail = self.get_detail()
            if detail:
                detail.unlink()
            self.unlink()
            return {
                "type": "ir.actions.act_window",
                "name": title_list,
                "res_model": "spp.change.request",
                "view_mode": "list,form",
                "target": "current",
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title_cannot,
                "message": message_cannot,
                "type": "warning",
            },
        }


class SPPChangeRequestTypeConflict(models.Model):
    """Extension of spp.change.request.type with conflict configuration."""

    _inherit = "spp.change.request.type"

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT DETECTION CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    enable_conflict_detection = fields.Boolean(
        default=False,
        help="Enable conflict checking for this CR type",
    )

    conflict_rule_ids = fields.One2many(
        "spp.cr.conflict.rule",
        "cr_type_id",
        string="Conflict Rules",
    )

    conflict_rule_count = fields.Integer(
        compute="_compute_conflict_rule_count",
        string="Conflict Rules",
    )

    @api.depends("conflict_rule_ids")
    def _compute_conflict_rule_count(self):
        for rec in self:
            rec.conflict_rule_count = len(rec.conflict_rule_ids)

    # ══════════════════════════════════════════════════════════════════════════
    # DUPLICATE DETECTION CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    enable_duplicate_detection = fields.Boolean(
        default=False,
        help="Enable duplicate checking for this CR type",
    )

    duplicate_detection_config_id = fields.Many2one(
        "spp.cr.duplicate.config",
        string="Duplicate Detection Config",
        ondelete="set null",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_view_conflict_rules(self):
        """View conflict rules for this CR type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Conflict Rules - %s") % self.name,
            "res_model": "spp.cr.conflict.rule",
            "view_mode": "list,form",
            "domain": [("cr_type_id", "=", self.id)],
            "context": {"default_cr_type_id": self.id},
        }

    def action_configure_duplicate_detection(self):
        """Open or create duplicate detection configuration."""
        self.ensure_one()

        if self.duplicate_detection_config_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Duplicate Detection - %s") % self.name,
                "res_model": "spp.cr.duplicate.config",
                "res_id": self.duplicate_detection_config_id.id,
                "view_mode": "form",
                "target": "new",
            }
        else:
            # Create new config
            config = self.env["spp.cr.duplicate.config"].create(
                {
                    "cr_type_id": self.id,
                }
            )
            self.duplicate_detection_config_id = config.id
            return {
                "type": "ir.actions.act_window",
                "name": _("Duplicate Detection - %s") % self.name,
                "res_model": "spp.cr.duplicate.config",
                "res_id": config.id,
                "view_mode": "form",
                "target": "new",
            }
