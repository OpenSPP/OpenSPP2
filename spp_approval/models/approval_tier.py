import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ApprovalTier(models.Model):
    """Defines a single tier within a multi-tier approval workflow.

    Each tier represents one approval stage that must be completed
    before moving to the next tier.
    """

    _name = "spp.approval.tier"
    _description = "Approval Tier"
    _order = "definition_id, sequence"

    name = fields.Char(required=True, help="Display name for this tier (e.g., 'Validator', 'Manager')")
    sequence = fields.Integer(default=10, help="Order in which tiers are processed")

    definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        required=True,
        ondelete="cascade",
    )

    # Approval configuration (mirrors base definition fields)
    approval_type = fields.Selection(
        [
            ("group", "Security Group"),
            ("user", "Specific Users"),
            ("manager", "Submitter's Manager"),
            ("field", "Field on Record"),
        ],
        string="Approver Type",
        required=True,
        default="group",
    )

    approval_group_id = fields.Many2one(
        "res.groups",
        string="Approver Group",
        help="Security group whose members can approve at this tier",
    )

    approval_user_ids = fields.Many2many(
        "res.users",
        "spp_approval_tier_user_rel",
        "tier_id",
        "user_id",
        string="Approvers",
        help="Specific users who can approve at this tier",
    )

    approval_field = fields.Char(
        string="Approver Field",
        help="Field name on the record containing the approver (e.g., 'manager_id')",
    )

    is_require_all = fields.Boolean(
        string="Require All Approvers",
        default=False,
        help="If checked, ALL designated approvers must approve. Otherwise, ANY one approver is sufficient.",
    )

    min_approvers = fields.Integer(
        string="Minimum Approvers",
        default=1,
        help="Minimum number of approvers required (when is_require_all is False)",
    )

    can_self_approve = fields.Boolean(
        string="Can Self-Approve",
        default=False,
        help="Allow the submitter to approve at this tier if they are a designated approver",
    )

    notify_on_pending = fields.Boolean(
        string="Notify When Pending",
        default=True,
        help="Send notification to approvers when this tier becomes pending",
    )

    sla_hours = fields.Integer(
        string="SLA (Hours)",
        default=0,
        help="Expected hours to complete this tier (0 = no SLA)",
    )

    is_blocking = fields.Boolean(
        string="Blocking",
        default=True,
        help="If unchecked, workflow continues to next tier without waiting for this tier's approval. "
        "Useful for informational/FYI tiers.",
    )

    active = fields.Boolean(default=True)

    @api.constrains("approval_type", "approval_group_id", "approval_user_ids", "approval_field")
    def _check_approver_config(self):
        """Ensure approver configuration is valid for the selected type."""
        for tier in self:
            if tier.approval_type == "group" and not tier.approval_group_id:
                raise ValidationError(_("Tier '%s': Please select an approver group.") % tier.name)
            if tier.approval_type == "user" and not tier.approval_user_ids:
                raise ValidationError(_("Tier '%s': Please select at least one approver.") % tier.name)
            if tier.approval_type == "field" and not tier.approval_field:
                raise ValidationError(_("Tier '%s': Please specify the approver field.") % tier.name)

    @api.constrains("min_approvers")
    def _check_min_approvers(self):
        """Ensure min_approvers is valid."""
        for tier in self:
            if tier.min_approvers < 1:
                raise ValidationError(_("Minimum approvers must be at least 1."))

    def get_approvers(self, record):
        """Get the users who can approve at this tier for the given record.

        Args:
            record: The record being approved

        Returns:
            res.users recordset of eligible approvers
        """
        self.ensure_one()
        approvers = self.env["res.users"]

        if self.approval_type == "group":
            if self.approval_group_id:
                approvers = self.approval_group_id.user_ids

        elif self.approval_type == "user":
            approvers = self.approval_user_ids

        elif self.approval_type == "manager":
            # Get submitter's manager
            submitter = getattr(record, "submitted_by_id", None) or record.create_uid
            if (
                submitter
                and hasattr(submitter, "employee_id")
                and submitter.employee_id
                and submitter.employee_id.parent_id
            ):
                approvers = submitter.employee_id.parent_id.user_id

        elif self.approval_type == "field":
            if self.approval_field and hasattr(record, self.approval_field):
                field_value = getattr(record, self.approval_field)
                if field_value:
                    # Check if field value is already res.users
                    if hasattr(field_value, "_name") and field_value._name == "res.users":
                        approvers = field_value
                    # Otherwise check if it has a user_id field (e.g., hr.employee)
                    elif hasattr(field_value, "user_id") and field_value.user_id:
                        approvers = field_value.user_id

        # Filter out submitter if self-approval not allowed
        if not self.can_self_approve and hasattr(record, "submitted_by_id") and record.submitted_by_id:
            approvers = approvers - record.submitted_by_id

        return approvers.filtered(lambda u: u.active)
