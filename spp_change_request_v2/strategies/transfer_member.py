import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyTransferMember(models.AbstractModel):
    """Custom apply strategy for Transfer Member CR type."""

    _name = "spp.cr.apply.transfer_member"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Transfer Member"

    def apply(self, change_request):
        """Transfer member from source group to target group."""
        source_group = change_request.registrant_id
        if not source_group.is_group:
            raise UserError(_("Source registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.membership_id:
            raise UserError(_("No member selected for transfer."))

        if not detail.target_group_id:
            raise UserError(_("No target group selected."))

        if not detail.target_group_id.is_group:
            raise UserError(_("Target must be a group."))

        membership = detail.membership_id
        individual = membership.individual
        target_group = detail.target_group_id

        # Verify membership is still active
        if membership.status != "active":
            raise UserError(_("Membership is already inactive."))

        # Check if individual already exists in target group
        existing = self.env["spp.group.membership"].search(
            [
                ("group", "=", target_group.id),
                ("individual", "=", individual.id),
                ("status", "=", "active"),
            ],
            limit=1,
        )
        if existing:
            raise UserError(_("Individual is already a member of the target group."))

        # End membership in source group
        # Ensure ended_date is not before start_date (can happen with same-day operations)
        transfer_datetime = fields.Datetime.to_datetime(detail.transfer_date)
        if membership.start_date and transfer_datetime < membership.start_date:
            transfer_datetime = membership.start_date
        membership.write({"ended_date": transfer_datetime, "active": False})

        # Create membership in target group
        new_membership_vals = {
            "group": target_group.id,
            "individual": individual.id,
            "start_date": transfer_datetime,
        }
        if detail.new_role_id:
            new_membership_vals["membership_type_ids"] = [Command.link(detail.new_role_id.id)]

        self.env["spp.group.membership"].create(new_membership_vals)

        _logger.info(
            "Transferred member partner_id=%s from group partner_id=%s to group partner_id=%s via CR %s",
            individual.id,
            source_group.id,
            target_group.id,
            change_request.name,
        )

        return True

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "transfer_member",
            "member_name": detail.member_name,
            "source_group": detail.source_group_name,
            "target_group": detail.target_group_name,
            "new_role": detail.new_role_id.display if detail.new_role_id else None,
            "transfer_date": str(detail.transfer_date),
            "reason": detail.transfer_reason,
        }
