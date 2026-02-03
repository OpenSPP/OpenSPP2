import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyAddMember(models.AbstractModel):
    """Custom apply strategy for Add Member CR type."""

    _name = "spp.cr.apply.add_member"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Add Group Member"

    def apply(self, change_request):
        """Create individual and add as group member."""
        group = change_request.registrant_id
        if not group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        # Validate required fields
        if not detail.member_name:
            raise UserError(_("Member name is required to add a new member."))

        # Create the individual
        individual_vals = {
            "name": detail.member_name,
            "given_name": detail.given_name,
            "family_name": detail.family_name,
            "birthdate": detail.birthdate,
            "phone": detail.phone,
            "is_registrant": True,
            "is_group": False,
        }

        # Handle gender field - Many2one to spp.vocabulary.code
        if detail.gender_id:
            individual_vals["gender_id"] = detail.gender_id.id

        _logger.info(
            "Creating individual from CR %s for registrant_id=%s",
            change_request.name,
            change_request.registrant_id.id,
        )
        individual = self.env["res.partner"].create(individual_vals)
        individual.name_change()

        # Create group membership
        membership_vals = {
            "group": group.id,
            "individual": individual.id,
            "start_date": fields.Date.today(),
        }

        # Handle relationship/membership type
        if detail.relationship_id:
            membership_vals["membership_type_ids"] = [Command.link(detail.relationship_id.id)]

        self.env["spp.group.membership"].create(membership_vals)

        # Store reference to created individual
        detail.write({"created_individual_id": individual.id})

        _logger.info(
            "Added member partner_id=%s to group partner_id=%s via CR %s",
            individual.id,
            group.id,
            change_request.name,
        )

        return True

    def preview(self, change_request):
        """Preview what will be created."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "create_member",
            "member_name": detail.member_name,
            "group": change_request.registrant_id.name,
            "relationship": detail.relationship_id.name if detail.relationship_id else None,
        }
