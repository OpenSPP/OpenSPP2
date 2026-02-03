import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyCreateGroup(models.AbstractModel):
    """Custom apply strategy for Create Group CR type."""

    _name = "spp.cr.apply.create_group"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Create New Group"

    def apply(self, change_request):
        """Create a new group/household."""
        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.group_name:
            raise UserError(_("Group name is required."))

        # Prepare group values
        group_vals = {
            "name": detail.group_name,
            "is_registrant": True,
            "is_group": True,
            "street": detail.address_line1,
            "street2": detail.address_line2,
            "city": detail.city,
            "state_id": detail.state_id.id if detail.state_id else False,
            "zip": detail.postal_code,
            "country_id": detail.country_id.id if detail.country_id else False,
            "phone": detail.phone,
            "email": detail.email,
        }

        if detail.group_type_id:
            group_vals["group_type_id"] = detail.group_type_id.id

        # Create the group
        group = self.env["res.partner"].create(group_vals)

        _logger.info(
            "Created group partner_id=%s (%s) via CR %s",
            group.id,
            group.name,
            change_request.name,
        )

        # Handle head of household
        head_individual = None
        if detail.create_new_head:
            # Create new individual as head
            if not detail.head_name:
                raise UserError(_("Head name is required when creating new head."))

            head_vals = {
                "name": detail.head_name,
                "given_name": detail.head_given_name,
                "family_name": detail.head_family_name,
                "birthdate": detail.head_birthdate,
                "phone": detail.head_phone,
                "is_registrant": True,
                "is_group": False,
            }
            if detail.head_gender_id:
                head_vals["gender_id"] = detail.head_gender_id.id

            head_individual = self.env["res.partner"].create(head_vals)
            head_individual.name_change()
            _logger.info(
                "Created head individual partner_id=%s for group partner_id=%s",
                head_individual.id,
                group.id,
            )
        elif detail.head_individual_id:
            head_individual = detail.head_individual_id

        # Create head membership if we have a head
        if head_individual:
            head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
            membership_vals = {
                "group": group.id,
                "individual": head_individual.id,
                "start_date": fields.Datetime.now(),
            }
            if head_type:
                membership_vals["membership_type_ids"] = [Command.link(head_type.id)]

            self.env["spp.group.membership"].create(membership_vals)
            _logger.info(
                "Added head partner_id=%s to group partner_id=%s",
                head_individual.id,
                group.id,
            )

        # Store reference to created group
        detail.write({"created_group_id": group.id})

        # Update the change request's registrant_id to point to the new group
        change_request.write({"registrant_id": group.id})

        return True

    def preview(self, change_request):
        """Preview what will be created."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        head_name = None
        if detail.create_new_head:
            head_name = detail.head_name
        elif detail.head_individual_id:
            head_name = detail.head_individual_id.name

        return {
            "_action": "create_group",
            "group_name": detail.group_name,
            "group_type": detail.group_type_id.display if detail.group_type_id else None,
            "head_of_household": head_name,
            "create_new_head": detail.create_new_head,
            "address": f"{detail.address_line1 or ''}, {detail.city or ''}".strip(", "),
        }
