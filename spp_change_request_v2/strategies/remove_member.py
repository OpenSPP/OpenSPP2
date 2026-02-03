import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyRemoveMember(models.AbstractModel):
    """Custom apply strategy for Remove Member CR type."""

    _name = "spp.cr.apply.remove_member"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Remove Group Member"

    def apply(self, change_request):
        """End membership for the specified member."""
        group = change_request.registrant_id
        if not group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.membership_id:
            raise UserError(_("No membership selected for removal."))

        membership = detail.membership_id

        # Verify membership is still active
        if membership.status != "active":
            raise UserError(_("Membership is already inactive."))

        # Convert date to datetime for ended_date field
        # Ensure ended_date is not before start_date (can happen with same-day operations)
        end_datetime = fields.Datetime.to_datetime(detail.end_date)
        if membership.start_date and end_datetime < membership.start_date:
            end_datetime = membership.start_date

        # End the membership
        membership.write(
            {
                "ended_date": end_datetime,
                "active": False,
            }
        )

        _logger.info(
            "Removed member partner_id=%s from group partner_id=%s via CR %s (reason: %s)",
            membership.individual.id,
            group.id,
            change_request.name,
            detail.end_reason,
        )

        return True

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "remove_member",
            "member_name": detail.member_name,
            "group": change_request.registrant_id.name,
            "end_date": str(detail.end_date),
            "reason": detail.end_reason,
        }
