# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.job_worker.delay import group

from ..programs import SPPProgram
from .pagination_utils import compute_id_ranges

_logger = logging.getLogger(__name__)


class ProgramManager(models.Model):
    _name = "spp.program.manager"
    _description = "Program Manager"
    _inherit = "spp.manager.mixin"

    program_id = fields.Many2one("spp.program", "Program", ondelete="cascade")

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = ("spp.program.manager.default", "Default")
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class BaseProgramManager(models.AbstractModel):
    _name = "spp.base.program.manager"
    _description = "Base Program Manager"

    MIN_ROW_JOB_QUEUE = 200
    MAX_ROW_JOB_QUEUE = 10000

    name = fields.Char("Manager Name", required=True)
    program_id = fields.Many2one("spp.program", string="Program", required=True)

    def last_cycle(self):
        """
        Returns the last cycle of the program
        Returns:
            cycle: the last cycle of the program
        """
        # TODO: implement this
        # sort the program's cycle by sequence and return the last one
        raise NotImplementedError()

    def new_cycle(self):
        """
        Create the next cycle of the program
        Returns:
            cycle: the newly created cycle
        """
        raise NotImplementedError()

    def enroll_eligible_registrants(self, state=None):
        """
        This method is used to enroll the beneficiaries in a program.
        Returns:
            bool: True if the beneficiaries were enrolled, False otherwise.
        """
        raise NotImplementedError()

    def mark_enroll_eligible_as_done(self):
        """Complete the enrollment of eligible beneficiaries.
        Base :meth:`mark_enroll_eligible_as_done`.
        This is executed when all the jobs are completed.
        Post a message in the chatter.
        :return:
        """
        self.ensure_one()
        program = self.program_id
        program._release_operation_lock()
        try:
            program.message_post(body=_("Eligibility check finished."))
        except Exception:
            _logger.exception("Failed to post completion chatter on program %s", program.id)

        # Compute Statistics
        program._compute_eligible_beneficiary_count()
        program._compute_beneficiary_count()

    def mark_enroll_eligible_as_failed(self):
        """Run via on_error() when async eligibility enrollment fails."""
        self.ensure_one()
        program = self.program_id
        program._release_operation_lock()
        try:
            program.message_post(body=_("Eligibility check failed."))
        except Exception:
            _logger.exception("Failed to post failure chatter on program %s", program.id)


class DefaultProgramManager(models.Model):
    _name = "spp.program.manager.default"
    _inherit = ["spp.base.program.manager", "spp.manager.source.mixin"]
    _description = "Default Program Manager"

    @api.model
    def default_get(self, fields_list):
        """Default the manager name to its method-specific label."""
        res = super().default_get(fields_list)
        if "name" in fields_list:
            res.setdefault("name", _("Default Program Manager"))
        return res

    number_of_cycles = fields.Integer(default=1)
    copy_last_cycle_on_new_cycle = fields.Boolean(string="Copy previous cycle", default=True)

    #  TODO: review 'calendar.recurrence' module, it seem the way to go for managing the recurrence
    # recurrence_id = fields.Many2one('calendar.recurrence', related='event_id.recurrence_id')

    def last_cycle(self):
        """
        Returns the last cycle of the program
        Returns:
            cycle: the last cycle of the program
        """
        cycles = self.env["spp.cycle"].search([("program_id", "=", self.program_id.id)], order="sequence desc", limit=1)
        return cycles and cycles[0] or None

    def new_cycle(self):
        """
        Create the next cycle of the program
        Returns:
            cycle: the newly created cycle
        """
        self.ensure_one()

        for rec in self:
            cycles = self.env["spp.cycle"].search([("program_id", "=", rec.program_id.id)])
            _logger.debug("cycles: %s", cycles)
            cm = rec.program_id.get_manager(SPPProgram.MANAGER_CYCLE)
            if len(cycles) == 0:
                _logger.debug("cycle manager: %s", cm)
                new_cycle = cm.new_cycle("Cycle 1", datetime.now(), 1)
            else:
                last_cycle = rec.last_cycle()
                new_sequence = last_cycle.sequence + 1
                start_date = last_cycle.end_date + timedelta(days=1)
                new_cycle = cm.new_cycle(
                    f"Cycle {new_sequence}",
                    start_date,
                    new_sequence,
                )

            # Copy the enrolled beneficiaries
            if new_cycle is not None:
                program_beneficiaries = rec.program_id.get_beneficiaries("enrolled").mapped("partner_id.id")
                cm.add_beneficiaries(new_cycle, program_beneficiaries, "enrolled")
            return new_cycle

    def enroll_eligible_registrants(self, state=None):
        self.ensure_one()
        # if state is None:
        #    states = ["draft"]
        if isinstance(state, str):
            states = [state]
        else:
            states = state

        program = self.program_id
        members_count = program.get_beneficiaries(state=states, count=True)
        _logger.debug("members: %s", members_count)

        eligibility_managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        if len(eligibility_managers) == 0:
            raise UserError(_("No Eligibility Manager defined."))
        elif members_count < self.MIN_ROW_JOB_QUEUE:
            count = self._enroll_eligible_registrants(state, do_count=True)
            un_enrolled_count = program.get_beneficiaries(state="not_eligible", count=True)
            enrolled_count = program.get_beneficiaries(state="enrolled", count=True)
            if (program.beneficiaries_count == enrolled_count) and not count:
                message = _("No new beneficiaries enrolled.")
            else:
                message = _(f"Enrolled Beneficiaries: {count} successfully and {un_enrolled_count} unsuccessfully.")
            kind = "success"
            sticky = False
        else:
            self._enroll_eligible_registrants_async(state, members_count)
            message = _("Eligibility check of %s beneficiaries started.", members_count)
            kind = "warning"
            sticky = True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Enrollment"),
                "message": message,
                "sticky": sticky,
                "type": kind,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def _enroll_eligible_registrants_async(self, states, members_count):
        self.ensure_one()
        _logger.debug("members: %s", members_count)
        program = self.program_id
        program.message_post(body=_("Eligibility check of %s beneficiaries started.", members_count))
        program._acquire_operation_lock("Eligibility check of beneficiaries")

        if isinstance(states, str):
            states = [states]

        # Mirror get_beneficiaries: when states is None/empty, no state filter is
        # applied (i.e. all states). Otherwise restrict to the given states.
        if states:
            where_clause = "program_id = %s AND state IN %s"
            params = (program.id, tuple(states))
        else:
            where_clause = "program_id = %s"
            params = (program.id,)

        id_ranges = compute_id_ranges(
            self.env.cr,
            "spp_program_membership",
            where_clause,
            params,
            self.MAX_ROW_JOB_QUEUE,
        )

        jobs = []
        for min_id, max_id in id_ranges:
            jobs.append(
                self.delayable(
                    channel="program_manager",
                    identity_key=f"enroll_eligible_{program.id}_{min_id}",
                )._enroll_eligible_registrants(states, min_id=min_id, max_id=max_id)
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable(channel="statistics_refresh").mark_enroll_eligible_as_done())
        main_job.on_error(self.delayable(channel="statistics_refresh").mark_enroll_eligible_as_failed())
        main_job.delay()

    def _enroll_eligible_registrants(self, states, offset=0, limit=None, min_id=None, max_id=None, do_count=False):
        """Enroll Eligible Registrants

        :param states: List of states to be used in domain filter
        :param offset: Optional integer value for the ORM search offset (deprecated, use min_id/max_id)
        :param limit: Optional integer value for the ORM search limit (deprecated, use min_id/max_id)
        :param min_id: Minimum record ID for ID-range pagination (inclusive)
        :param max_id: Maximum record ID for ID-range pagination (inclusive)
        :param do_count: Boolean - set to False to not run compute functions
        :return: Integer - count of not enrolled members
        """
        program = self.program_id
        members = program.get_beneficiaries(
            state=states, offset=offset, limit=limit, min_id=min_id, max_id=max_id, order="id"
        )

        member_before = members

        eligibility_managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        # TODO: Handle multiple eligibility managers properly
        for el in eligibility_managers:
            members = el.enroll_eligible_registrants(members)
        # enroll the one not already enrolled:
        # Exclude members that are duplicated or exited — those states
        # should only be changed through their own workflows.
        _logger.debug("members filtered: %s", members)
        not_enrolled = members.filtered(lambda m: m.state not in ("enrolled", "duplicated", "exited"))
        _logger.debug("not_enrolled: %s", not_enrolled)

        # Run pre-enrollment hooks (e.g., scoring eligibility checks).
        # Members that fail the hook are moved to not_eligible.
        hook_failed = self.env["spp.program.membership"]
        for member in not_enrolled:
            try:
                program._pre_enrollment_hook(member.partner_id)
            except (ValidationError, UserError) as e:
                _logger.info(
                    "Pre-enrollment hook rejected registrant %s: %s",
                    member.partner_id.id,
                    str(e),
                )
                hook_failed |= member

        # Re-check already-enrolled members against the current
        # eligibility rules. "Verify Eligibility" implies a fresh check;
        # an enrolled registrant whose data became invalid (e.g. a
        # required indicator now resolves to a sentinel string) must be
        # demoted, not silently kept enrolled. We work from `member_before`
        # (pre-eligibility-manager-filter) so an enrolled member that the
        # default manager would silently skip is still re-checked here.
        # See OP#838.
        already_enrolled = member_before.filtered(lambda m: m.state == "enrolled")
        re_verify_failed = self.env["spp.program.membership"]
        for member in already_enrolled:
            try:
                program._pre_enrollment_hook(member.partner_id)
            except (ValidationError, UserError) as e:
                _logger.info(
                    "Re-verify rejected enrolled registrant %s: %s",
                    member.partner_id.id,
                    str(e),
                )
                re_verify_failed |= member

        enrollable = not_enrolled - hook_failed
        if hook_failed:
            hook_failed.write({"state": "not_eligible"})

        if re_verify_failed:
            re_verify_failed.write({"state": "not_eligible"})

        enrollable.write(
            {
                "state": "enrolled",
                "enrollment_date": fields.Datetime.now(),
            }
        )

        # Run post-enrollment hooks (e.g., auto-score on enrollment)
        for member in enrollable:
            program._post_enrollment_hook(member.partner_id)
        # dis-enroll the one not eligible anymore:
        enrolled_members_ids = members.ids
        members_to_remove = member_before.filtered(
            lambda m: m.state not in ("not_eligible", "duplicated", "exited") and m.id not in enrolled_members_ids
        )
        # _logger.debug("members_to_remove: %s", members_to_remove)
        members_to_remove.write(
            {
                "state": "not_eligible",
            }
        )

        if do_count:
            # Compute Statistics
            program._compute_eligible_beneficiary_count()
            program._compute_beneficiary_count()

        return len(enrollable)
