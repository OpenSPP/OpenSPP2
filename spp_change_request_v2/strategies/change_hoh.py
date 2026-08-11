import logging

from odoo import Command, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyChangeHOH(models.AbstractModel):
    """Custom apply strategy for Change Head of Household CR type."""

    _name = "spp.cr.apply.change_hoh"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Change Head of Household"

    def apply(self, change_request):
        """Change the head of household."""
        group = change_request.registrant_id
        if not group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.new_head_membership_id:
            raise UserError(_("No new head of household selected."))

        head_kind = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        if not head_kind:
            raise UserError(
                _(
                    "Head of Household membership type not found. "
                    "Please configure 'head' membership type in the vocabulary."
                )
            )

        # Find current head membership
        current_head_membership = self.env["spp.group.membership"].search(
            [
                ("group", "=", group.id),
                ("membership_type_ids", "in", [head_kind.id]),
                ("status", "=", "active"),
            ],
            limit=1,
        )

        new_head_membership = detail.new_head_membership_id

        # Remove head role from current head
        if current_head_membership:
            current_roles = current_head_membership.membership_type_ids - head_kind
            new_roles = current_roles
            # Add the new role for previous head if specified
            if detail.previous_head_new_role_id:
                new_roles = current_roles | detail.previous_head_new_role_id

            current_head_membership.write(
                {
                    "membership_type_ids": [Command.set(new_roles.ids)],
                }
            )
            _logger.info(
                "Removed head role from partner_id=%s in group partner_id=%s",
                current_head_membership.individual.id,
                group.id,
            )

        # Add head role to new head
        new_roles = new_head_membership.membership_type_ids | head_kind
        new_head_membership.write(
            {
                "membership_type_ids": [Command.set(new_roles.ids)],
            }
        )

        _logger.info(
            "Changed head of household for group partner_id=%s from partner_id=%s to partner_id=%s via CR %s",
            group.id,
            current_head_membership.individual.id if current_head_membership else None,
            new_head_membership.individual.id,
            change_request.name,
        )

        return True

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "change_head_of_household",
            "group": change_request.registrant_id.name,
            "current_head": detail.current_head_id.name if detail.current_head_id else None,
            "new_head": detail.new_head_id.name if detail.new_head_id else None,
            "reason": detail.reason,
        }
