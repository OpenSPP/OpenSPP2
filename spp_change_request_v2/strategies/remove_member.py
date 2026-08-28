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

        # OP#872: removal applies immediately on approval (the End Date field was
        # dropped as it had no effect on effectivity).
        membership.write(
            {
                "ended_date": fields.Datetime.now(),
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

        reason_label = None
        if detail.end_reason:
            reason_label = dict(detail.fields_get(["end_reason"])["end_reason"]["selection"]).get(detail.end_reason)

        return {
            "_action": "remove_member",
            "_header": _("The following individual is to be removed."),
            _("Member"): detail.individual_id.display_name if detail.individual_id else None,
            _("Group"): change_request.registrant_id.display_name,
            _("Reason for Removal"): reason_label,
            _("Additional Information"): detail.remarks or None,
        }
