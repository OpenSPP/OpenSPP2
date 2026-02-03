import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyExitRegistrant(models.AbstractModel):
    """Custom apply strategy for Exit Registrant CR type."""

    _name = "spp.cr.apply.exit_registrant"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Exit Registrant"

    def apply(self, change_request):
        """Deactivate/exit the registrant.

        IMPORTANT: The disabled flag must be set LAST to ensure all membership
        operations complete before record rules hide the registrant's data.
        """
        registrant = change_request.registrant_id
        if not registrant:
            raise UserError(_("No registrant found."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        # End active memberships if requested (BEFORE disabling registrant)
        if detail.is_end_active_memberships and not registrant.is_group:
            end_datetime = fields.Datetime.to_datetime(detail.exit_date)
            memberships = self.env["spp.group.membership"].search(
                [
                    ("individual", "=", registrant.id),
                    ("status", "=", "active"),
                ]
            )
            for membership in memberships:
                # Ensure ended_date is not before start_date
                actual_end = end_datetime
                if membership.start_date and end_datetime < membership.start_date:
                    actual_end = membership.start_date
                membership.write({"ended_date": actual_end})
            if memberships:
                _logger.info(
                    "Ended %d active memberships for partner_id=%s",
                    len(memberships),
                    registrant.id,
                )

        # If it's a group, end all member memberships
        if registrant.is_group and detail.is_end_active_memberships:
            end_datetime = fields.Datetime.to_datetime(detail.exit_date)
            memberships = self.env["spp.group.membership"].search(
                [
                    ("group", "=", registrant.id),
                    ("status", "=", "active"),
                ]
            )
            for membership in memberships:
                # Ensure ended_date is not before start_date
                actual_end = end_datetime
                if membership.start_date and end_datetime < membership.start_date:
                    actual_end = membership.start_date
                membership.write({"ended_date": actual_end})
            if memberships:
                _logger.info(
                    "Ended %d memberships in exited group partner_id=%s",
                    len(memberships),
                    registrant.id,
                )

        # Deactivate the registrant LAST (after all membership operations)
        # This ensures record rules don't hide data during the apply process
        registrant.write(
            {
                "disabled": detail.exit_date,
            }
        )

        _logger.info(
            "Exited registrant partner_id=%s via CR %s (reason: %s)",
            registrant.id,
            change_request.name,
            detail.exit_reason,
        )

        return True

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "exit_registrant",
            "registrant": change_request.registrant_id.name,
            "exit_date": str(detail.exit_date),
            "reason": detail.exit_reason,
            "end_memberships": detail.is_end_active_memberships,
            "active_membership_count": detail.active_membership_count,
        }
