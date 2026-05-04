import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyAssignProgram(models.AbstractModel):
    """Custom apply strategy for the assign-to-program CR type.

    Creates an `spp.program.membership` record linking the CR's registrant to
    the program selected on the detail. The membership starts in `draft` so
    the program's own enrollment workflow can take over from there.
    """

    _name = "spp.cr.apply.assign_program"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Assign to Program"

    def validate(self, change_request):
        """Validate the CR can be applied. Raises UserError on any failure."""
        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found for this change request."))

        program = detail.program_id
        if not program:
            raise UserError(_("Program is required to assign a registrant."))

        registrant = change_request.registrant_id
        if not registrant:
            raise UserError(_("Registrant is required."))

        if registrant.disabled:
            raise UserError(_("Disabled registrants cannot be assigned to a program."))

        if program.state != "active":
            raise UserError(_("Only active programs can accept new registrants."))

        expected_target_type = "group" if registrant.is_group else "individual"
        if program.target_type != expected_target_type:
            raise UserError(
                _(
                    "Program '%(program)s' targets '%(program_target)s' "
                    "registrants but '%(registrant)s' is "
                    "'%(registrant_target)s'."
                )
                % {
                    "program": program.display_name,
                    "program_target": program.target_type,
                    "registrant": registrant.display_name,
                    "registrant_target": expected_target_type,
                }
            )

        existing = self.env["spp.program.membership"].search_count(
            [("partner_id", "=", registrant.id), ("program_id", "=", program.id)]
        )
        if existing:
            raise UserError(
                _("%(registrant)s is already in program %(program)s.")
                % {
                    "registrant": registrant.display_name,
                    "program": program.display_name,
                }
            )

    def apply(self, change_request):
        """Validate, then create the program membership."""
        self.validate(change_request)

        detail = change_request.get_detail()
        registrant = change_request.registrant_id
        program = detail.program_id

        membership = self.env["spp.program.membership"].create({"partner_id": registrant.id, "program_id": program.id})
        detail.write({"created_membership_id": membership.id})

        _logger.info(
            "Created program membership id=%s for registrant_id=%s, program_id=%s via CR %s",
            membership.id,
            registrant.id,
            program.id,
            change_request.name,
        )
        return True

    def preview(self, change_request):
        """Preview what will happen on apply."""
        detail = change_request.get_detail()
        if not detail or not detail.program_id:
            return {}

        return {
            "_action": "create_program_membership",
            "registrant": change_request.registrant_id.display_name,
            "program": detail.program_id.display_name,
            "initial_state": "draft",
        }
