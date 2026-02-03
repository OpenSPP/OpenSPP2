import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class ApprovalMixinMultitier(models.AbstractModel):
    """Extend approval mixin to support multi-tier workflows."""

    _inherit = "spp.approval.mixin"

    # Multi-tier state tracking
    current_approval_tier_id = fields.Many2one(
        "spp.approval.tier",
        string="Current Approval Tier",
        compute="_compute_multitier_info",
    )

    current_tier_name = fields.Char(
        string="Current Tier",
        compute="_compute_multitier_info",
    )

    approval_tier_progress = fields.Float(
        string="Approval Progress (%)",
        compute="_compute_multitier_info",
    )

    is_multitier_approval = fields.Boolean(
        string="Multi-Tier Approval",
        compute="_compute_multitier_info",
    )

    def _compute_multitier_info(self):
        """Compute multi-tier approval information."""
        for record in self:
            # Find active review
            active_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]

            if active_review and active_review.is_multitier:
                record.is_multitier_approval = True
                record.current_approval_tier_id = active_review.current_tier_id
                record.current_tier_name = active_review.current_tier_name
                record.approval_tier_progress = active_review.tier_progress
            else:
                record.is_multitier_approval = False
                record.current_approval_tier_id = False
                record.current_tier_name = False
                record.approval_tier_progress = 0

    def _compute_approval_permissions(self):
        """Override to check multi-tier permissions."""
        for record in self:
            _logger.warning(
                "Multi-tier _compute_approval_permissions called for %s %s by user %s",
                record._name,
                record.id,
                self.env.user.name,
            )
            record.can_submit = record.approval_state == "draft"
            record.can_approve = False
            record.can_reject = False

            if record.approval_state == "pending":
                # Find active review
                all_reviews = record.approval_review_ids
                pending_reviews = record.approval_review_ids.filtered(lambda r: r.status == "pending")
                active_review = pending_reviews[:1]

                _logger.warning(
                    "Multi-tier permission check for %s %s: total_reviews=%s, pending_reviews=%s, active_review=%s",
                    record._name,
                    record.id,
                    len(all_reviews),
                    len(pending_reviews),
                    bool(active_review),
                )

                if all_reviews:
                    review_statuses = all_reviews.mapped(lambda r: f"{r.id}:{r.status}")
                    _logger.warning("Review statuses for %s %s: %s", record._name, record.id, review_statuses)

                _logger.warning(
                    "Multi-tier permission check: active_review found for %s %s: %s (is_multitier=%s)",
                    record._name,
                    record.id,
                    bool(active_review),
                    active_review.is_multitier if active_review else False,
                )

                if not active_review:
                    continue

                if active_review.is_multitier:
                    # Multi-tier: check current tier approvers
                    approvers = active_review.get_current_tier_approvers()
                    _logger.warning(
                        "Multi-tier current tier approvers for %s %s: tier=%s, approvers=%s, user=%s in approvers=%s",
                        record._name,
                        record.id,
                        active_review.current_tier_name,
                        approvers.mapped("name"),
                        self.env.user.name,
                        self.env.user in approvers,
                    )
                else:
                    # Single-tier: use the definition from the review (already resolved at submit)
                    # Use sudo to read definition as users may have limited access
                    definition = active_review.sudo().definition_id
                    approvers = definition.get_approvers(record) if definition else self.env["res.users"]
                    _logger.warning(
                        "Single-tier approvers for %s %s: definition=%s, approvers=%s, user=%s in approvers=%s",
                        record._name,
                        record.id,
                        definition.name if definition else None,
                        approvers.mapped("name"),
                        self.env.user.name,
                        self.env.user in approvers,
                    )

                if self.env.user in approvers:
                    record.can_approve = True
                    record.can_reject = True
                    _logger.warning("Multi-tier permission result for %s %s: can_approve=True", record._name, record.id)
                else:
                    _logger.warning(
                        "Multi-tier permission result for %s %s: can_approve=False (user not in approvers)",
                        record._name,
                        record.id,
                    )

    def action_approve(self, comment=None):
        """Override to handle multi-tier approval."""
        for record in self:
            _logger.warning(
                "Multi-tier action_approve called for %s %s by user %s", record._name, record.id, self.env.user.name
            )
            _logger.warning("Multi-tier action_approve: calling _check_can_approve for %s %s", record._name, record.id)
            record._check_can_approve()
            _logger.warning("Multi-tier action_approve: _check_can_approve passed for %s %s", record._name, record.id)

            # Find active review
            active_review = record.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]

            if active_review and active_review.is_multitier:
                _logger.warning(
                    "Multi-tier approval: approving tier %s for %s %s",
                    active_review.current_tier_name,
                    record._name,
                    record.id,
                )
                # Multi-tier: approve current tier
                active_review.action_approve_tier(comment=comment)

                # Check if all tiers are now complete
                if active_review.status == "approved":
                    _logger.warning("All tiers approved, completing approval for %s %s", record._name, record.id)
                    record._do_approve(comment=comment)
            else:
                _logger.warning("Single-tier approval for %s %s", record._name, record.id)
                # Single-tier: original behavior
                record._do_approve(comment=comment)

    def action_reject(self):
        """Override to open rejection wizard (works for both single and multi-tier)."""
        self.ensure_one()
        self._check_can_reject()

        return {
            "name": _("Reject"),
            "type": "ir.actions.act_window",
            "res_model": "spp.approval.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def _do_reject(self, reason):
        """Override to handle multi-tier rejection."""
        self.ensure_one()

        # Find active review
        active_review = self.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]

        if active_review and active_review.is_multitier:
            # Multi-tier: reject current tier (cascades to review)
            active_review.action_reject_tier(reason)

        # Update record state (same for both modes)
        self.write(
            {
                "approval_state": "rejected",
                "rejected_by_id": self.env.user.id,
                "rejected_date": fields.Datetime.now(),
                "rejection_reason": reason,
            }
        )

        # Complete activity
        self.activity_feedback(
            ["spp_approval.mail_activity_approval_required"],
            feedback=reason or _("Rejected"),
        )

        # Hook for custom logic
        self._on_reject(reason)

        # Notify submitter
        self._notify_approval_result("rejected", reason)

    def get_approval_summary(self):
        """Get a summary of approval status including tier information.

        Returns:
            dict with approval status information
        """
        self.ensure_one()

        summary = {
            "state": self.approval_state,
            "submitted_by": self.submitted_by_id.name if self.submitted_by_id else None,
            "submitted_date": self.submitted_date,
            "is_multitier": self.is_multitier_approval,
        }

        if self.approval_state == "approved":
            summary.update(
                {
                    "approved_by": self.approved_by_id.name if self.approved_by_id else None,
                    "approved_date": self.approved_date,
                }
            )
        elif self.approval_state == "rejected":
            summary.update(
                {
                    "rejected_by": self.rejected_by_id.name if self.rejected_by_id else None,
                    "rejected_date": self.rejected_date,
                    "rejection_reason": self.rejection_reason,
                }
            )
        elif self.approval_state == "pending":
            active_review = self.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]

            if active_review and active_review.is_multitier:
                summary.update(
                    {
                        "current_tier": self.current_tier_name,
                        "progress": self.approval_tier_progress,
                        "total_tiers": active_review.total_tiers,
                        "completed_tiers": active_review.completed_tiers,
                        "tier_details": [
                            {
                                "name": tr.tier_name,
                                "status": tr.status,
                                "approved_by": [u.name for u in tr.approved_by_ids],
                            }
                            for tr in active_review.tier_review_ids.sorted("sequence")
                        ],
                    }
                )

        return summary
