import logging

import psycopg2

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import mute_logger

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

    def _program_accessible_to_requester(self, change_request, program):
        """Whether the CR *requester* (``create_uid``) may target ``program``.

        Bound to the requester - the identity whose authority the assignment
        rides on - not the apply-time actor, which is sudo (and, after the
        apply-authorization guard, a manager who may span companies). Mirrors
        the write-time ``_check_program_access`` company scope. Returns True for
        a company-shared program (``company_id`` False). No-op in single-company
        deployments (every program's company is in every user's ``company_ids``).
        """
        requester = change_request.create_uid
        return not program.company_id or program.company_id in requester.company_ids

    def _check_program_access_at_apply(self, change_request, program):
        """Raise unless the requester may target ``program``.

        Re-asserts access at the sudo sink, so a program written before the
        write-time constraint existed (the module shipped in released tags
        without it), imported, or slipped in under a sudo prefill, still cannot
        be applied cross-company.
        """
        if not self._program_accessible_to_requester(change_request, program):
            raise UserError(
                _("The change request creator does not have access to program '%(program)s'.")
                % {"program": program.display_name}
            )

    def validate(self, change_request):
        """Validate the CR can be applied. Raises UserError on any failure.

        This runs under ``sudo`` (see ``spp.change.request._do_apply``). Program
        access is enforced primarily at selection time by
        ``spp.cr.detail.assign_program._check_program_access`` (a write-time
        constraint in the user's own context), but that constraint cannot cover
        a stored value it never saw: records written before the constraint
        existed (the module shipped in released tags without it), an import, or
        a future sudo prefill that sets ``program_id`` without triggering
        constraints. So re-assert program access here, at the sink, before the
        privileged membership create - see ``_check_program_access_at_apply``.
        """
        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found for this change request."))

        program = detail.program_id
        if not program:
            raise UserError(_("Program is required to assign a registrant."))

        self._check_program_access_at_apply(change_request, program)

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

        # `validate()` checks the (registrant, program) pair is unique, but a
        # concurrent transaction can insert the same pair between that read
        # and the create below. The DB unique constraint on
        # spp.program.membership(partner_id, program_id) catches the race;
        # wrap the create in a savepoint so the parent transaction stays
        # usable, and translate the psycopg2 error into the same friendly
        # UserError the validate() path produces.
        try:
            with self.env.cr.savepoint(), mute_logger("odoo.sql_db"):
                membership = self.env["spp.program.membership"].create(
                    {"partner_id": registrant.id, "program_id": program.id}
                )
        except psycopg2.errors.UniqueViolation as exc:
            raise UserError(
                _("%(registrant)s is already in program %(program)s.")
                % {
                    "registrant": registrant.display_name,
                    "program": program.display_name,
                }
            ) from exc
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
        """Preview what will happen on apply.

        Runs under sudo (via ``_capture_preview_snapshot`` / the preview HTML),
        so redact the program name for a stored program the requester cannot
        access - otherwise a pre-existing out-of-scope ``program_id`` (see
        ``_check_program_access_at_apply``) would leak the cross-company
        program's name here even though it can never be applied. Preview must
        stay non-throwing, so redact rather than raise.
        """
        detail = change_request.get_detail()
        if not detail or not detail.program_id:
            return {}

        program = detail.program_id
        if not self._program_accessible_to_requester(change_request, program):
            return {
                "_action": "create_program_membership",
                "registrant": change_request.registrant_id.display_name,
                "program": _("(program not accessible to the requester)"),
                "initial_state": "draft",
            }

        return {
            "_action": "create_program_membership",
            "registrant": change_request.registrant_id.display_name,
            "program": program.display_name,
            "initial_state": "draft",
        }
