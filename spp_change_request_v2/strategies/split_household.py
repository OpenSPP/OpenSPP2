import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplySplitHousehold(models.AbstractModel):
    """Custom apply strategy for Split Household CR type."""

    _name = "spp.cr.apply.split_household"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Split Household"

    def apply(self, change_request):
        """Split household by creating new group and transferring members."""
        source_group = change_request.registrant_id
        if not source_group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.members_to_split_ids:
            raise UserError(_("No members selected for split."))

        if not detail.new_head_membership_id:
            raise UserError(_("No head selected for new household."))

        if not detail.new_group_name:
            raise UserError(_("New household name is required."))

        # Create new group
        group_vals = {
            "name": detail.new_group_name,
            "is_registrant": True,
            "is_group": True,
        }

        # Set group type (use source type if not specified)
        if detail.new_group_type_id:
            group_vals["group_type_id"] = detail.new_group_type_id.id
        elif source_group.group_type_id:
            group_vals["group_type_id"] = source_group.group_type_id.id

        # Set address
        if detail.copy_address:
            group_vals.update(
                {
                    "street": source_group.street,
                    "street2": source_group.street2,
                    "city": source_group.city,
                    "state_id": source_group.state_id.id if source_group.state_id else False,
                    "zip": source_group.zip,
                    "country_id": source_group.country_id.id if source_group.country_id else False,
                    "phone": source_group.phone,
                    "email": source_group.email,
                }
            )
        else:
            group_vals.update(
                {
                    "street": detail.address_line1,
                    "street2": detail.address_line2,
                    "city": detail.city,
                    "state_id": detail.state_id.id if detail.state_id else False,
                    "zip": detail.postal_code,
                    "country_id": detail.country_id.id if detail.country_id else False,
                    "phone": detail.phone,
                    "email": detail.email,
                }
            )

        new_group = self.env["res.partner"].create(group_vals)
        _logger.info(
            "Created new group partner_id=%s (%s) from split of partner_id=%s",
            new_group.id,
            new_group.name,
            source_group.id,
        )

        # Get head membership kind from vocabulary
        head_kind = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

        # Transfer members to new group
        effective_datetime = fields.Datetime.to_datetime(detail.effective_date)
        new_head_individual = detail.new_head_membership_id.individual

        for membership in detail.members_to_split_ids:
            individual = membership.individual

            # End membership in source group
            # Ensure ended_date is not before start_date (can happen with same-day operations)
            actual_end = effective_datetime
            if membership.start_date and effective_datetime < membership.start_date:
                actual_end = membership.start_date
            membership.write({"ended_date": actual_end, "active": False})

            # Create membership in new group
            new_membership_vals = {
                "group": new_group.id,
                "individual": individual.id,
                "start_date": effective_datetime,
            }

            # Set head role for new head
            if individual == new_head_individual and head_kind:
                new_membership_vals["membership_type_ids"] = [Command.link(head_kind.id)]
            else:
                # Keep existing roles except head
                existing_roles = membership.membership_type_ids
                if head_kind:
                    existing_roles = existing_roles - head_kind
                if existing_roles:
                    new_membership_vals["membership_type_ids"] = [Command.set(existing_roles.ids)]

            self.env["spp.group.membership"].create(new_membership_vals)

            _logger.info(
                "Transferred member partner_id=%s from group %s to new group %s",
                individual.id,
                source_group.id,
                new_group.id,
            )

        # Store reference to created group
        detail.write({"created_group_id": new_group.id})

        _logger.info(
            "Split household: moved %d members from partner_id=%s to new partner_id=%s via CR %s",
            len(detail.members_to_split_ids),
            source_group.id,
            new_group.id,
            change_request.name,
        )

        return True

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        members = []
        for m in detail.members_to_split_ids:
            members.append(m.individual.name)

        return {
            "_action": "split_household",
            "source_group": detail.source_group_name,
            "new_group_name": detail.new_group_name,
            "new_head": detail.new_head_membership_id.individual.name if detail.new_head_membership_id else None,
            "members_to_move": members,
            "members_count": detail.members_to_split_count,
            "remaining_count": detail.remaining_members_count,
            "reason": detail.split_reason,
        }
