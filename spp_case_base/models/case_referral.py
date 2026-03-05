"""Case Referral Model."""

from odoo import _, api, fields, models


class CaseReferral(models.Model):
    """Referrals to external services for cases."""

    _name = "spp.case.referral"
    _description = "Case Referral"
    _order = "referral_date desc"

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        required=True,
        ondelete="cascade",
    )

    referral_date = fields.Date(
        string="Referral Date",
        required=True,
        default=fields.Date.context_today,
    )

    referred_by_id = fields.Many2one(
        "res.users",
        string="Referred By",
        required=True,
        default=lambda self: self.env.user,
    )

    service_name = fields.Char(
        string="Service Name",
        required=True,
        help="Name of the service being referred to",
    )

    provider_name = fields.Char(
        string="Provider Name",
        help="Name of the organization or person providing the service",
    )

    reason = fields.Text(
        string="Reason for Referral",
        required=True,
        help="Reason or need for the referral",
    )

    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("completed", "Completed"),
        ],
        string="Status",
        required=True,
        default="pending",
    )

    outcome = fields.Text(
        string="Outcome",
        help="Result or outcome of the referral",
    )

    follow_up_date = fields.Date(
        string="Follow-up Date",
        help="Date to follow up on the referral",
    )

    # Related fields for easy access
    case_worker_id = fields.Many2one(
        "res.users",
        string="Case Worker",
        related="case_id.case_worker_id",
        store=True,
        readonly=True,
    )

    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        related="case_id.partner_id",
        store=True,
        readonly=True,
    )

    # Computed fields
    is_overdue = fields.Boolean(
        string="Is Overdue",
        compute="_compute_is_overdue",
        store=False,
    )

    @api.depends("follow_up_date", "status")
    def _compute_is_overdue(self):
        """Check if follow-up is overdue."""
        today = fields.Date.context_today(self)
        for referral in self:
            referral.is_overdue = (
                referral.follow_up_date
                and referral.follow_up_date < today
                and referral.status not in ["completed", "rejected"]
            )

    def action_accept(self):
        """Mark referral as accepted."""
        for referral in self:
            referral.status = "accepted"
        return True

    def action_reject(self):
        """Mark referral as rejected."""
        for referral in self:
            referral.status = "rejected"
        return True

    def action_complete(self):
        """Mark referral as completed."""
        for referral in self:
            referral.status = "completed"
        return True

    def _compute_display_name(self):
        """Compute display name for referrals."""
        for referral in self:
            if referral.service_name and referral.client_id:
                referral.display_name = f"{referral.service_name} - {referral.client_id.name}"
            elif referral.service_name:
                referral.display_name = referral.service_name
            else:
                referral.display_name = f"Referral #{referral.id}"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to log referral creation."""
        referrals = super().create(vals_list)
        # Post message to case chatter
        for referral in referrals:
            if referral.case_id:
                referral.case_id.message_post(
                    body=_("Referral created to %(service)s", service=referral.service_name),
                    subject=_("New Referral"),
                )
        return referrals
