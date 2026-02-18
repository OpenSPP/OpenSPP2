import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class ApprovalDefinition(models.Model):
    """Configurable approval workflow definitions.

    Defines who can approve and under what conditions for each model.
    """

    _name = "spp.approval.definition"
    _description = "Approval Workflow Definition"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # Target model
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        domain="['|', ('is_mail_thread', '=', True), ('model', '=like', 'x_spp_cr_detail_%')]",
    )
    model = fields.Char(
        string="Model Name",
        related="model_id.model",
        store=True,
        index=True,
    )

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Who can approve
    approval_type = fields.Selection(
        [
            ("group", "Security Group"),
            ("user", "Specific Users"),
            ("manager", "Manager of Submitter"),
            ("field", "Dynamic Field"),
        ],
        default="group",
        required=True,
    )
    approval_group_id = fields.Many2one(
        "res.groups",
        string="Approval Group",
    )
    approval_user_ids = fields.Many2many(
        "res.users",
        string="Approval Users",
    )
    approval_field_id = fields.Many2one(
        "ir.model.fields",
        string="Approval Field",
        domain="[('model_id', '=', model_id), ('relation', '=', 'res.users')]",
        help="Field on the model that contains the user who can approve",
    )

    # When this definition applies (domain filter)
    domain = fields.Char(
        default="[]",
        help="Domain to filter which records need this approval. Leave empty to apply to all records.",
    )

    # Behavior settings
    is_require_comment = fields.Boolean(
        default=False,
        help="Require a comment when approving or rejecting",
    )
    notify_on_submit = fields.Boolean(
        default=True,
        help="Notify approvers when a record is submitted",
    )
    notify_on_approve = fields.Boolean(
        default=True,
        help="Notify submitter when approved",
    )
    notify_on_reject = fields.Boolean(
        default=True,
        help="Notify submitter when rejected",
    )
    auto_approve_same_user = fields.Boolean(
        default=False,
        help="Auto-approve if submitter is also an approver",
    )

    # SLA tracking
    sla_days = fields.Integer(
        string="SLA (Days)",
        default=0,
        help="Expected days to complete approval. 0 = no SLA.",
    )
    escalation_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Escalate To",
        help="Definition to escalate to if SLA is exceeded",
    )

    # Emergency and freeze handling
    is_emergency_bypass_allowed = fields.Boolean(
        string="Emergency Bypass Allowed",
        default=False,
        help="Can be bypassed during declared emergencies",
    )
    is_respect_system_freeze = fields.Boolean(
        string="Respect System Freeze",
        default=True,
        help="Block approvals during system-wide freeze periods",
    )

    @api.constrains("domain")
    def _check_domain(self):
        """Validate the domain syntax."""
        for record in self:
            if record.domain:
                try:
                    ast.literal_eval(record.domain)
                except (ValueError, SyntaxError) as e:
                    raise ValidationError(_("Invalid domain syntax: %s") % str(e)) from e

    @api.constrains("approval_type", "approval_group_id", "approval_user_ids", "approval_field_id")
    def _check_approval_config(self):
        """Ensure approval configuration is complete."""
        for record in self:
            if record.approval_type == "group" and not record.approval_group_id:
                raise ValidationError(_("Please select an approval group."))
            if record.approval_type == "user" and not record.approval_user_ids:
                raise ValidationError(_("Please select at least one approval user."))
            if record.approval_type == "field" and not record.approval_field_id:
                raise ValidationError(_("Please select an approval field."))

    def get_approvers(self, record):
        """Get the users who can approve a specific record.

        Args:
            record: The record being approved

        Returns:
            res.users recordset
        """
        self.ensure_one()

        if self.approval_type == "group":
            return self.approval_group_id.user_ids
        elif self.approval_type == "user":
            return self.approval_user_ids
        elif self.approval_type == "manager":
            # Get submitter's manager
            submitter = record.create_uid
            if hasattr(submitter, "employee_id") and submitter.employee_id.parent_id:
                return submitter.employee_id.parent_id.user_id
            return self.env["res.users"]
        elif self.approval_type == "field":
            if self.approval_field_id:
                field_name = self.approval_field_id.name
                if hasattr(record, field_name):
                    user = getattr(record, field_name)
                    if user and user._name == "res.users":
                        return user
        return self.env["res.users"]

    def matches_record(self, record):
        """Check if this definition applies to a record.

        Args:
            record: The record to check

        Returns:
            bool
        """
        self.ensure_one()

        if not self.domain or self.domain == "[]":
            return True

        try:
            domain = ast.literal_eval(self.domain)
            matching = self.env[record._name].search([("id", "=", record.id)] + domain)
            return bool(matching)
        except (ValueError, SyntaxError) as e:
            # Invalid domain syntax - log warning and default to matching
            _logger.warning(
                "Invalid domain syntax in approval definition %s: %s. Defaulting to match all records.",
                self.name,
                str(e),
            )
            return True

    @api.model
    def get_definitions_for_model(self, model_name, company_id=None):
        """Get all active definitions for a model.

        Args:
            model_name: The model name (e.g., 'res.partner')
            company_id: Optional company ID

        Returns:
            spp.approval.definition recordset
        """
        domain = [
            ("model", "=", model_name),
            ("active", "=", True),
        ]
        if company_id:
            domain.append("|")
            domain.append(("company_id", "=", False))
            domain.append(("company_id", "=", company_id))

        return self.search(domain, order="sequence")

    def unlink(self):
        """Prevent managers from deleting approval definitions. Only admin can delete."""
        for _record in self:  # noqa: B007
            # Administrators can delete
            if self.env.user.has_group("base.group_system") or self.env.user.has_group(
                "spp_approval.group_approval_admin"
            ):
                continue
            # Managers cannot delete (even though they have perm_unlink=1 in access control)
            if self.env.user.has_group("spp_approval.group_approval_manager"):
                raise AccessError(
                    _("Managers cannot delete approval definitions. Only administrators can delete them.")
                )
        return super().unlink()
