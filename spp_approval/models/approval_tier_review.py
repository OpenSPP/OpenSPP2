import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApprovalTierReview(models.Model):
    """Tracks the approval status for each tier of a review.

    One record per tier per review, tracking who approved/rejected
    and when.
    """

    _name = "spp.approval.tier.review"
    _description = "Approval Tier Review"
    _order = "review_id, sequence"

    review_id = fields.Many2one(
        "spp.approval.review",
        string="Approval Review",
        required=True,
        ondelete="cascade",
    )

    tier_id = fields.Many2one(
        "spp.approval.tier",
        string="Approval Tier",
        required=True,
        ondelete="restrict",
    )

    sequence = fields.Integer(related="tier_id.sequence", store=True)
    tier_name = fields.Char(related="tier_id.name", store=True)

    status = fields.Selection(
        [
            ("waiting", "Waiting"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("skipped", "Skipped"),
        ],
        default="waiting",
        required=True,
        index=True,
    )

    # Approval tracking
    approved_by_ids = fields.Many2many(
        "res.users",
        "spp_approval_tier_review_approver_rel",
        "tier_review_id",
        "user_id",
        string="Approved By",
        readonly=True,
    )

    approved_date = fields.Datetime(string="First Approval Date", readonly=True)
    completed_date = fields.Datetime(string="Completed Date", readonly=True)

    rejected_by_id = fields.Many2one(
        "res.users",
        string="Rejected By",
        readonly=True,
    )
    rejected_date = fields.Datetime(string="Rejected Date", readonly=True)
    rejection_reason = fields.Text(string="Rejection Reason", readonly=True)

    comment = fields.Text(string="Comments")

    # SLA tracking
    sla_deadline = fields.Datetime(string="SLA Deadline")
    is_sla_breached = fields.Boolean(compute="_compute_sla_breached", store=True)

    # Computed
    approver_count = fields.Integer(compute="_compute_approver_count")
    required_approvals = fields.Integer(compute="_compute_required_approvals")

    @api.depends("approved_by_ids")
    def _compute_approver_count(self):
        for record in self:
            record.approver_count = len(record.approved_by_ids)

    @api.depends("tier_id.is_require_all", "tier_id.min_approvers", "tier_id")
    def _compute_required_approvals(self):
        for record in self:
            if record.tier_id.is_require_all:
                # Count total possible approvers
                # This is a simplification - in practice would need to evaluate at runtime
                record.required_approvals = record.tier_id.min_approvers
            else:
                record.required_approvals = record.tier_id.min_approvers

    @api.depends("sla_deadline", "status")
    def _compute_sla_breached(self):
        now = fields.Datetime.now()
        for record in self:
            if record.status == "pending" and record.sla_deadline:
                record.is_sla_breached = now > record.sla_deadline
            else:
                record.is_sla_breached = False

    def action_approve(self, comment=None):
        """Approve this tier (by current user)."""
        self.ensure_one()

        if self.status != "pending":
            raise UserError(_("Only pending tiers can be approved."))

        user = self.env.user
        approvers = self.tier_id.get_approvers(self.review_id._get_record())

        # Log using IDs only to avoid PII in logs
        _logger.warning(
            "Tier review approval check for tier_id=%s: approver_ids=%s, user_id=%s in approvers=%s",
            self.tier_id.id,
            approvers.ids,
            user.id,
            user in approvers,
        )

        if user not in approvers:
            _logger.error(
                "User ID %s not authorized to approve tier_id=%s; approver_ids=%s",
                user.id,
                self.tier_id.id,
                approvers.ids,
            )
            raise UserError(_("You are not authorized to approve at this tier."))

        if user in self.approved_by_ids:
            raise UserError(_("You have already approved at this tier."))

        # Record approval
        vals = {
            "approved_by_ids": [(4, user.id)],
            "comment": comment if comment else self.comment,
        }

        if not self.approved_date:
            vals["approved_date"] = fields.Datetime.now()

        self.write(vals)

        # Check if tier is complete
        self._check_tier_completion()

    def _check_tier_completion(self):
        """Check if this tier has enough approvals to be complete."""
        self.ensure_one()

        if self.status != "pending":
            return

        tier = self.tier_id
        approval_count = len(self.approved_by_ids)

        is_complete = False

        if tier.is_require_all:
            # Need all designated approvers
            record = self.review_id._get_record()
            all_approvers = tier.get_approvers(record)
            is_complete = all_approvers and all_approvers <= self.approved_by_ids
        else:
            # Need minimum number
            is_complete = approval_count >= tier.min_approvers

        if is_complete:
            self.write(
                {
                    "status": "approved",
                    "completed_date": fields.Datetime.now(),
                }
            )
            # Trigger next tier or final approval (use sudo for system callback)
            self.review_id.sudo()._on_tier_approved(self)

    def action_reject(self, reason):
        """Reject this tier (and the entire review)."""
        self.ensure_one()

        if self.status != "pending":
            raise UserError(_("Only pending tiers can be rejected."))

        user = self.env.user
        approvers = self.tier_id.get_approvers(self.review_id._get_record())

        if user not in approvers:
            raise UserError(_("You are not authorized to reject at this tier."))

        self.write(
            {
                "status": "rejected",
                "rejected_by_id": user.id,
                "rejected_date": fields.Datetime.now(),
                "rejection_reason": reason,
                "completed_date": fields.Datetime.now(),
            }
        )

        # Trigger review rejection (use sudo for system callback)
        self.review_id.sudo()._on_tier_rejected(self, reason)

    def action_activate(self):
        """Activate this tier (make it pending)."""
        self.ensure_one()

        if self.status != "waiting":
            raise UserError(_("Only waiting tiers can be activated."))

        vals = {
            "status": "pending",
        }

        # Set SLA deadline
        if self.tier_id.sla_hours:
            vals["sla_deadline"] = fields.Datetime.add(
                fields.Datetime.now(),
                hours=self.tier_id.sla_hours,
            )

        self.write(vals)

        # Create activities for approvers
        if self.tier_id.notify_on_pending:
            self._create_tier_activities()

    def _create_tier_activities(self):
        """Create mail activities for approvers at this tier."""
        self.ensure_one()

        record = self.review_id._get_record()
        if not record:
            return

        approvers = self.tier_id.get_approvers(record)
        if not approvers:
            return

        activity_type = self.env.ref(
            "spp_approval.mail_activity_approval_required",
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        for user in approvers:
            deadline = fields.Date.today()
            if self.tier_id.sla_hours:
                deadline = fields.Date.add(
                    deadline,
                    days=(self.tier_id.sla_hours // 24) or 1,
                )

            # Use sudo() for activity creation since this is a system action
            record.sudo().activity_schedule(
                "spp_approval.mail_activity_approval_required",
                user_id=user.id,
                date_deadline=deadline,
                summary=_("Approval Required (Tier: %s): %s")
                % (
                    self.tier_id.name,
                    record.display_name,
                ),
            )
