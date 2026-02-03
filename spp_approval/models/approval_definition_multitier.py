import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ApprovalDefinitionMultitier(models.Model):
    """Extend approval definition to support multi-tier workflows."""

    _inherit = "spp.approval.definition"

    use_multitier = fields.Boolean(
        string="Multi-Tier Approval",
        default=False,
        help="Enable sequential multi-tier approval workflow",
    )

    tier_ids = fields.One2many(
        "spp.approval.tier",
        "definition_id",
        string="Approval Tiers",
    )

    tier_count = fields.Integer(compute="_compute_tier_count")

    @api.depends("tier_ids")
    def _compute_tier_count(self):
        for record in self:
            record.tier_count = len(record.tier_ids)

    @api.constrains("use_multitier", "tier_ids")
    def _check_multitier_config(self):
        """Ensure multi-tier definitions have at least one tier."""
        for definition in self:
            if definition.use_multitier and not definition.tier_ids:
                raise ValidationError(_("Multi-tier approval requires at least one approval tier."))

    @api.constrains("approval_type", "approval_group_id", "approval_user_ids", "approval_field_id")
    def _check_approval_config(self):
        """Override to skip validation for multi-tier definitions."""
        for record in self:
            # Skip single-tier validation for multi-tier definitions
            if record.use_multitier:
                continue
            # Call original validation logic
            if record.approval_type == "group" and not record.approval_group_id:
                raise ValidationError(_("Please select an approval group."))
            if record.approval_type == "user" and not record.approval_user_ids:
                raise ValidationError(_("Please select at least one approval user."))
            if record.approval_type == "field" and not record.approval_field_id:
                raise ValidationError(_("Please select an approval field."))

    @api.onchange("use_multitier")
    def _onchange_use_multitier(self):
        """Clear single-tier approver settings when enabling multi-tier."""
        if self.use_multitier:
            self.approval_group_id = False
            self.approval_user_ids = [Command.clear()]
            self.approval_field_id = False

    def get_approvers(self, record):
        """Override to return approvers for first pending tier in multi-tier mode."""
        self.ensure_one()

        if not self.use_multitier:
            return super().get_approvers(record)

        # In multi-tier mode, return approvers for the first tier
        # (actual tier-based approvers are determined at runtime)
        first_tier = self.tier_ids.sorted("sequence")[:1]
        if first_tier:
            return first_tier.get_approvers(record)

        return self.env["res.users"]

    def get_ordered_tiers(self):
        """Get tiers in sequence order."""
        self.ensure_one()
        return self.tier_ids.sorted("sequence")
