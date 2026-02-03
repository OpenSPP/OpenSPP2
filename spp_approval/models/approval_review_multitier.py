import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApprovalReviewMultitier(models.Model):
    """Extend approval review to support multi-tier tracking."""

    _inherit = "spp.approval.review"

    # Multi-tier tracking
    tier_review_ids = fields.One2many(
        "spp.approval.tier.review",
        "review_id",
        string="Tier Reviews",
    )

    current_tier_id = fields.Many2one(
        "spp.approval.tier",
        string="Current Tier",
        compute="_compute_current_tier",
        store=True,
    )

    current_tier_name = fields.Char(
        related="current_tier_id.name",
        string="Current Tier Name",
    )

    total_tiers = fields.Integer(compute="_compute_tier_progress")
    completed_tiers = fields.Integer(compute="_compute_tier_progress")
    tier_progress = fields.Float(
        compute="_compute_tier_progress",
        string="Progress (%)",
    )

    is_multitier = fields.Boolean(
        related="definition_id.use_multitier",
        store=True,
    )

    @api.depends("tier_review_ids.status")
    def _compute_current_tier(self):
        for review in self:
            if not review.definition_id.use_multitier:
                review.current_tier_id = False
                continue

            # Find first pending tier
            pending = review.tier_review_ids.filtered(lambda t: t.status == "pending").sorted("sequence")[:1]

            if pending:
                review.current_tier_id = pending.tier_id
            else:
                review.current_tier_id = False

    @api.depends("tier_review_ids", "tier_review_ids.status")
    def _compute_tier_progress(self):
        for review in self:
            if not review.definition_id.use_multitier:
                review.total_tiers = 0
                review.completed_tiers = 0
                review.tier_progress = 0
                continue

            total = len(review.tier_review_ids)
            completed = len(review.tier_review_ids.filtered(lambda t: t.status in ("approved", "skipped")))

            review.total_tiers = total
            review.completed_tiers = completed
            review.tier_progress = (completed / total * 100) if total else 0

    @api.model_create_multi
    def create(self, vals_list):
        """Override to create tier reviews for multi-tier definitions."""
        reviews = super().create(vals_list)

        for review in reviews:
            if review.definition_id.use_multitier:
                review._create_tier_reviews()

        return reviews

    def _create_tier_reviews(self):
        """Create tier review records for all tiers in the definition."""
        self.ensure_one()

        if not self.definition_id.use_multitier:
            return

        tiers = self.definition_id.get_ordered_tiers()

        tier_reviews = []
        for tier in tiers:
            tier_reviews.append(
                {
                    "review_id": self.id,
                    "tier_id": tier.id,
                    "status": "waiting",
                }
            )

        if tier_reviews:
            self.env["spp.approval.tier.review"].create(tier_reviews)

            # Activate first tier(s) - handles non-blocking tiers automatically
            first_tier_review = self.tier_review_ids.sorted("sequence")[:1]
            if first_tier_review:
                first_tier_review.action_activate()
                # If the first tier is non-blocking, continue to next tier(s)
                if not first_tier_review.tier_id.is_blocking:
                    self._activate_next_tier_or_complete()

    def _get_record(self):
        """Get the actual record being reviewed."""
        self.ensure_one()
        if self.model and self.res_id:
            return self.env[self.model].browse(self.res_id).exists()
        return None

    def _on_tier_approved(self, tier_review):
        """Called when a tier is approved. Activates next tier or completes review."""
        self.ensure_one()
        self._activate_next_tier_or_complete()

    def _activate_next_tier_or_complete(self):
        """Activate next tier(s), handling non-blocking tiers.

        Non-blocking tiers are activated for notification purposes but don't
        hold up the workflow. The workflow continues to the next blocking tier
        or completes if all remaining tiers are non-blocking or approved.
        """
        self.ensure_one()

        while True:
            # Find next waiting tier
            next_tier_review = self.tier_review_ids.filtered(lambda t: t.status == "waiting").sorted("sequence")[:1]

            if not next_tier_review:
                # Check if all blocking tiers are approved
                blocking_incomplete = self.tier_review_ids.filtered(
                    lambda t: t.tier_id.is_blocking and t.status not in ("approved", "skipped")
                )
                if not blocking_incomplete:
                    # All blocking tiers complete - approve the review
                    self.action_approve(comment=_("All required tiers approved"))
                return

            # Activate the next tier
            next_tier_review.action_activate()

            # If this tier is blocking, stop here and wait for approval
            if next_tier_review.tier_id.is_blocking:
                return

            # Non-blocking tier: continue to next tier without waiting
            # Note: the tier stays in "pending" status for async approval,
            # but workflow continues immediately

    def _on_tier_rejected(self, tier_review, reason):
        """Called when a tier is rejected. Rejects the entire review."""
        self.ensure_one()

        # Mark remaining tiers as skipped
        waiting_tiers = self.tier_review_ids.filtered(lambda t: t.status == "waiting")
        waiting_tiers.sudo().write({"status": "skipped"})

        # Reject the review (use sudo since this is a system action triggered
        # by the multi-tier engine after individual tier approvals).
        self.sudo().action_reject(  # nosemgrep: odoo-sudo-without-context - Final review rejection is a system-level workflow transition after tier checks.
            comment=reason
        )

    def action_approve_tier(self, comment=None):
        """Approve the current tier."""
        self.ensure_one()

        if not self.definition_id.use_multitier:
            return self.action_approve(comment=comment)

        current = self.tier_review_ids.filtered(lambda t: t.status == "pending").sorted("sequence")[:1]

        if not current:
            raise UserError(_("No pending tier to approve."))

        current.action_approve(comment=comment)

    def action_reject_tier(self, reason):
        """Reject the current tier."""
        self.ensure_one()

        if not self.definition_id.use_multitier:
            return self.action_reject(comment=reason)

        current = self.tier_review_ids.filtered(lambda t: t.status == "pending").sorted("sequence")[:1]

        if not current:
            raise UserError(_("No pending tier to reject."))

        current.action_reject(reason)

    def get_current_tier_approvers(self):
        """Get approvers for the current pending tier."""
        self.ensure_one()

        if not self.definition_id.use_multitier:
            return self.definition_id.get_approvers(self._get_record())

        if not self.current_tier_id:
            return self.env["res.users"]

        record = self._get_record()
        if not record:
            return self.env["res.users"]

        return self.current_tier_id.get_approvers(record)
