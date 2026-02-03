from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ApprovalFreeze(models.Model):
    """System-wide approval freeze periods.

    Used to suspend approvals during regulatory periods such as:
    - Election bans
    - Audit periods
    - System maintenance
    - Regulatory holds
    """

    _name = "spp.approval.freeze"
    _description = "Approval Freeze Period"
    _order = "date_start desc"

    name = fields.Char(required=True)
    reason = fields.Selection(
        [
            ("election", "Election Ban Period"),
            ("audit", "Audit Period"),
            ("regulatory", "Regulatory Hold"),
            ("maintenance", "System Maintenance"),
            ("other", "Other"),
        ],
        required=True,
        default="other",
    )
    description = fields.Text(help="Detailed description of the freeze reason")

    date_start = fields.Datetime(required=True, default=fields.Datetime.now)
    date_end = fields.Datetime(required=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Leave empty to apply to all companies",
    )

    model_ids = fields.Many2many(
        "ir.model",
        string="Affected Models",
        help="Leave empty to affect all approval-enabled models",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("ended", "Ended"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        compute="_compute_state",
        store=True,
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        """Ensure date_end is after date_start."""
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end <= record.date_start:
                    raise ValidationError(_("End date must be after start date."))

    @api.depends("date_start", "date_end")
    def _compute_state(self):
        now = fields.Datetime.now()
        for record in self:
            if record.state == "cancelled":
                continue
            if record.date_end and record.date_end <= now:
                record.state = "ended"
            elif record.date_start and record.date_start <= now:
                record.state = "active"
            else:
                record.state = "draft"

    def action_activate(self):
        """Manually activate the freeze period."""
        for record in self:
            if record.state == "cancelled":
                raise UserError(_("Cannot activate a cancelled freeze period."))
            record.write({"date_start": fields.Datetime.now()})

    def action_end(self):
        """Manually end the freeze period."""
        for record in self:
            record.write({"date_end": fields.Datetime.now()})

    def action_cancel(self):
        """Cancel the freeze period."""
        self.write({"state": "cancelled"})

    @api.model
    def is_frozen(self, model_name=None, company_id=None):
        """Check if approvals are currently frozen.

        Args:
            model_name: Optional model name to check
            company_id: Optional company ID to check

        Returns:
            dict with 'frozen' boolean and 'reason' if frozen
        """
        now = fields.Datetime.now()
        domain = [
            ("date_start", "<=", now),
            ("date_end", ">=", now),
            ("state", "!=", "cancelled"),
        ]

        if company_id:
            domain.append("|")
            domain.append(("company_id", "=", False))
            domain.append(("company_id", "=", company_id))

        freezes = self.search(domain)

        for freeze in freezes:
            # Check if model is affected
            if model_name and freeze.model_ids:
                affected_models = freeze.model_ids.mapped("model")
                if model_name not in affected_models:
                    continue

            return {
                "frozen": True,
                "reason": freeze.name,
                "freeze_id": freeze.id,
                "date_end": freeze.date_end,
            }

        return {"frozen": False}

    def unlink(self):
        """Prevent managers from deleting freeze periods. Only admin can delete."""
        for _record in self:  # noqa: B007
            # Administrators can delete
            if self.env.user.has_group("base.group_system") or self.env.user.has_group(
                "spp_approval.group_approval_admin"
            ):
                continue
            # Managers cannot delete (even though they have perm_unlink=1 in access control)
            if self.env.user.has_group("spp_approval.group_approval_manager"):
                raise AccessError(_("Managers cannot delete freeze periods. Only administrators can delete them."))
        return super().unlink()
