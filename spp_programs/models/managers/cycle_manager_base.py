# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import calendar
import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.job_worker.delay import group

from .. import constants

_logger = logging.getLogger(__name__)


class CycleManager(models.Model):
    _name = "spp.cycle.manager"
    _description = "Cycle Manager"
    _inherit = "spp.manager.mixin"

    program_id = fields.Many2one("spp.program", "Program", ondelete="cascade")

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = ("spp.cycle.manager.default", "Default")
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class BaseCycleManager(models.AbstractModel):
    _name = "spp.base.cycle.manager"
    _description = "Base Cycle Manager"

    MIN_ROW_JOB_QUEUE = 200
    MAX_ROW_JOB_QUEUE = 2000

    name = fields.Char("Manager Name", required=True)
    program_id = fields.Many2one("spp.program", string="Program", required=True)

    auto_approve_entitlements = fields.Boolean(string="Auto-approve Entitlements", default=False)

    def check_eligibility(self, cycle, beneficiaries=None):
        """
        Validate the eligibility of each beneficiary for the cycle
        """
        raise NotImplementedError()

    def prepare_entitlements(self, cycle):
        """
        Prepare the entitlements for the cycle
        """
        raise NotImplementedError()

    def issue_payments(self, cycle):
        """
        Issue the payments based on entitlements for the cycle
        """
        raise NotImplementedError()

    def validate_entitlements(self, cycle, cycle_memberships):
        """
        Validate the entitlements for the cycle
        """
        raise NotImplementedError()

    def new_cycle(self, name, new_start_date, sequence):
        """
        Create a new cycle for the program
        """
        raise NotImplementedError()

    def mark_distributed(self, cycle):
        """
        Mark the cycle as distributed
        """
        raise NotImplementedError()

    def mark_ended(self, cycle):
        """
        Mark the cycle as ended
        """
        raise NotImplementedError()

    def mark_cancelled(self, cycle):
        """
        Mark the cycle as cancelled
        """
        raise NotImplementedError()

    def add_beneficiaries(self, cycle, beneficiaries, state="draft"):
        """
        Add beneficiaries to the cycle
        """
        raise NotImplementedError()

    def on_start_date_change(self, cycle):
        """
        Hook for when the start date change
        """
        raise NotImplementedError()

    def approve_cycle(self, cycle, auto_approve=False, entitlement_manager=None):
        """

        :param cycle:
        :param auto_approve:
        :param entitlement_manager:
        :return:
        """
        # Check if user is allowed to approve the cycle
        if cycle.state != "to_approve":
            message = _("Only 'to approve' cycles can be approved.")
            kind = "danger"

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cycle"),
                    "message": message,
                    "sticky": False,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

        # Check funds BEFORE approving cycle if auto_approve is enabled
        if auto_approve:
            if not entitlement_manager:
                raise UserError(_("Entitlement manager is required for auto-approve."))

            # Get pending entitlements
            if entitlement_manager.IS_CASH_ENTITLEMENT:
                entitlement_mdl = "spp.entitlement"
            else:
                entitlement_mdl = "spp.entitlement.inkind"

            entitlements = cycle.get_entitlements(["draft", "pending_validation"], entitlement_model=entitlement_mdl)

            if entitlements:
                # Check if there are sufficient funds for all entitlements
                if entitlement_manager.IS_CASH_ENTITLEMENT:
                    fund_check_result = self._check_sufficient_funds_for_entitlements(
                        cycle, entitlements, entitlement_manager
                    )
                    if fund_check_result:
                        # Return error notification if insufficient funds
                        return fund_check_result

        # Approve the cycle
        cycle.update(
            {
                "approved_date": fields.Datetime.now(),
                "approved_by": self.env.user.id,
                "state": cycle.STATE_APPROVED,
            }
        )
        # Running on_state_change because it is not triggered automatically with rec.update above
        self.on_state_change(cycle)

        # Approve entitlements
        if auto_approve:
            if entitlement_manager.IS_CASH_ENTITLEMENT:
                entitlement_mdl = "spp.entitlement"
            else:
                entitlement_mdl = "spp.entitlement.inkind"
            entitlements = cycle.get_entitlements(["draft", "pending_validation"], entitlement_model=entitlement_mdl)
            if entitlements:
                self.auto_approve_entitlements_update_reviews(entitlements)
                return entitlement_manager.validate_entitlements(cycle)
            else:
                message = _("Auto-approve entitlements is set but there are no entitlements to process.")
                kind = "warning"

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Entitlements"),
                    "message": message,
                    "sticky": True,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def _check_sufficient_funds_for_entitlements(self, cycle, entitlements, entitlement_manager):
        """
        Check if there are sufficient funds for all entitlements before approving the cycle.

        :param cycle: The cycle to approve
        :param entitlements: Entitlements to be approved
        :param entitlement_manager: The entitlement manager instance
        :return: Error notification dict if insufficient funds, None if sufficient
        """
        # Calculate total amount needed for all entitlements
        total_amount_needed = sum(entitlements.mapped("initial_amount"))

        # Get current fund balance
        fund_balance = entitlement_manager.check_fund_balance(cycle.program_id.id)

        # Check if funds are sufficient
        if fund_balance < total_amount_needed:
            message = _(
                "Insufficient funds for auto-approving entitlements!\n\n"
                "Program: %(program)s\n"
                "Available funds: %(available).2f\n"
                "Required funds: %(required).2f\n"
                "Shortage: %(shortage).2f\n\n"
                "Please ensure sufficient funds are available before approving the cycle."
            ) % {
                "program": cycle.program_id.name,
                "available": fund_balance,
                "required": total_amount_needed,
                "shortage": total_amount_needed - fund_balance,
            }

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Insufficient Funds"),
                    "message": message,
                    "sticky": True,
                    "type": "danger",
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

        return None

    def auto_approve_entitlements_update_reviews(self, entitlements):
        """Auto-approve entitlements and update the approval reviews."""
        for rec in entitlements:
            # Submit for approval if in draft state (creates approval review records)
            if rec.state == "draft":
                definition = rec._get_approval_definition()
                if definition:
                    rec.action_submit_for_approval()
                    # Flush and invalidate cache to see newly created approval_review_ids
                    self.env.cr.flush()
                    rec.invalidate_cache(["approval_review_ids"])

            # Update pending approval reviews to approved
            pending_reviews = rec.approval_review_ids.filtered(lambda r: r.status == "pending")
            if pending_reviews:
                pending_reviews.write(
                    {
                        "status": "approved",
                        "reviewer_id": self.env.user.id,
                        "review_date": fields.Datetime.now(),
                    }
                )

    def on_state_change(self, cycle):
        """

        :param cycle:
        :return:
        """
        if cycle.state == cycle.STATE_APPROVED:
            if not self.approval_definition_id:
                raise ValidationError(_("The cycle approval definition is not specified!"))
            else:
                if (
                    self.env.user.id != 1
                    and self.env.user.id not in self.approval_definition_id.approval_group_id.user_ids.ids
                ):
                    # Get the approver group name for a better error message
                    definition = cycle._get_approval_definition()
                    group_name = _("Unknown Group")

                    if definition:
                        if definition.use_multitier:
                            # Multi-tier: get current tier's group
                            active_review = cycle.approval_review_ids.filtered(lambda r: r.status == "pending")[:1]
                            if active_review and active_review.level_id and active_review.level_id.group_id:
                                group_name = active_review.level_id.group_id.name
                        elif definition.approval_group_id:
                            # Single-tier: show the approver group
                            group_name = definition.approval_group_id.name

                    raise ValidationError(
                        _(
                            "You are not authorized to approve this cycle.\n\n"
                            "Only users in the following group(s) can approve:\n%(groups)s"
                        )
                        % {
                            "groups": group_name,
                        }
                    )

    def _ensure_can_edit_cycle(self, cycle):
        """Base :meth:'_ensure_can_edit_cycle`
        Check if the cycle can be editted

        :param cycle: A recordset of cycle
        :return:
        """
        if cycle.state not in [cycle.STATE_DRAFT]:
            raise ValidationError(_("The Cycle is not in draft mode"))

    def mark_import_as_done(self, cycle, msg):
        """Complete the import of beneficiaries.
        Base :meth:`mark_import_as_done`.
        This is executed when all the jobs are completed.
        Post a message in the chatter.

        :param cycle: A recordset of cycle
        :param msg: A string to be posted in the chatter
        :return:
        """
        self.ensure_one()
        cycle.is_locked = False
        cycle.locked_reason = None
        cycle.message_post(body=msg)

        # Update Statistics
        cycle._compute_members_count()

    def mark_prepare_entitlement_as_done(self, cycle, msg):
        """Complete the preparation of entitlements.
        Base :meth:`mark_prepare_entitlement_as_done`.
        This is executed when all the jobs are completed.
        Post a message in the chatter.

        :param cycle: A recordset of cycle
        :param msg: A string to be posted in the chatter
        :return:
        """
        self.ensure_one()
        cycle.is_locked = False
        cycle.locked_reason = None
        cycle.message_post(body=msg)

        # Update Statistics
        cycle._compute_entitlements_count()

    def mark_check_eligibility_as_done(self, cycle):
        """Complete the enrollment of eligible beneficiaries.
        Base :meth:`mark_check_eligibility_as_done`.
        This is executed when all the jobs are completed.
        Post a message in the chatter.

        :param cycle: A recordset of cycle
        :return:
        """
        cycle.is_locked = False
        cycle.locked_reason = None
        cycle.message_post(body=_("Eligibility check finished."))

        # Compute Statistics
        cycle._compute_members_count()


class DefaultCycleManager(models.Model):
    _name = "spp.cycle.manager.default"
    _inherit = [
        "spp.base.cycle.manager",
        "spp.cycle.recurrence.mixin",
        "spp.manager.source.mixin",
    ]
    _description = "Default Cycle Manager"

    cycle_duration = fields.Integer(default=1, required=True, string="Recurrence")
    approver_group_id = fields.Many2one(
        comodel_name="res.groups",
        string="Approver Group",
        copy=True,
    )
    approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        copy=True,
        domain="[('model_id.model', '=', 'spp.cycle')]",
    )

    def check_eligibility(self, cycle, beneficiaries=None):
        """
        Default Cycle Manager eligibility checker

        :param cycle: The cycle that is being verified
        :type cycle: :class:`spp_programs.models.cycle.SPPCycle`
        :param beneficiaries: the beneficiaries that need to be verified.
                By Default the one with the state ``draft``
                or ``enrolled`` are verified.
        :type beneficiaries: list or None

        :return: The list of eligible beneficiaries
        :rtype: list
        Validate the eligibility of each beneficiary for the
            cycle using the configured manager(s)
        :class:`spp_programs.models.managers.eligibility_manager.BaseEligibilityManager`.
            If there is multiple managers
            for eligibility, each of them are run using the filtered list of eligible
            beneficiaries from the previous one.

        The ``state`` of beneficiaries is updated to either ``enrolled`` if they match the enrollment criteria
        or ``not_eligible`` in case they do not match them.


        """
        for rec in self:
            rec._ensure_can_edit_cycle(cycle)

            # Get all the draft, enrolled, and not eligible beneficiaries
            if beneficiaries is None:
                beneficiaries_count = cycle.get_beneficiaries(["draft", "enrolled", "not_eligible"], count=True)
            else:
                beneficiaries_count = len(beneficiaries)

            # Pre-compute cached variables before eligibility check
            # This ensures the cache is warm for fast SQL-based lookups
            rec._precompute_cycle_cached_variables(cycle, beneficiaries)

            if beneficiaries_count < self.MIN_ROW_JOB_QUEUE:
                count = self._check_eligibility(cycle, beneficiaries=beneficiaries, do_count=True)
                message = _("%s Beneficiaries enrolled.", count)
                kind = "success"
            else:
                self._check_eligibility_async(cycle, beneficiaries_count)
                message = _(
                    "Eligibility check of %s beneficiaries started.",
                    beneficiaries_count,
                )
                kind = "warning"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Enrollment"),
                    "message": message,
                    "sticky": True,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def _precompute_cycle_cached_variables(self, cycle, beneficiaries=None):
        """Pre-compute cached variables for cycle beneficiaries.

        This method is called before eligibility checks to warm the cache
        for variables with cache_strategy='ttl' or 'manual'. This enables
        fast SQL-based lookups during eligibility evaluation.

        Args:
            cycle: The cycle being processed
            beneficiaries: Optional list of beneficiary records. If None, uses all draft/enrolled.
        """
        try:
            # Check if spp_cel_domain module is installed
            if "spp.data.cache.manager" not in self.env:
                return

            # Get beneficiary IDs
            if beneficiaries is None:
                beneficiaries = cycle.get_beneficiaries(["draft", "enrolled", "not_eligible"])

            if not beneficiaries:
                return

            subject_ids = beneficiaries.mapped("partner_id.id")

            if not subject_ids:
                return

            # Pre-compute all cached variables
            cache_mgr = self.env["spp.data.cache.manager"]
            result = cache_mgr.precompute_cached_variables(
                subject_ids,
                period_key="current",
                program_id=cycle.program_id.id,
            )

            if result.get("success"):
                _logger.info(
                    "Pre-computed %d cached variables for cycle '%s' (%d subjects, %d values)",
                    result.get("variables_processed", 0),
                    cycle.name,
                    len(subject_ids),
                    result.get("total_computed", 0),
                )
            else:
                _logger.warning(
                    "Failed to pre-compute cached variables for cycle '%s': %s",
                    cycle.name,
                    result.get("error_message"),
                )

        except Exception as e:
            # Don't fail the eligibility check if pre-computation fails
            # The system will fall back to on-demand computation
            _logger.warning(
                "Error pre-computing cached variables for cycle '%s': %s",
                cycle.name,
                str(e),
                exc_info=True,
            )

    def _check_eligibility_async(self, cycle, beneficiaries_count):
        self.ensure_one()
        _logger.debug("Beneficiaries: %s", beneficiaries_count)
        cycle.message_post(body=_("Eligibility check of %s beneficiaries started.", beneficiaries_count))
        cycle.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})

        jobs = []
        for i in range(0, beneficiaries_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(
                self.delayable(channel="cycle")._check_eligibility(cycle, offset=i, limit=self.MAX_ROW_JOB_QUEUE)
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable(channel="cycle").mark_check_eligibility_as_done(cycle))
        main_job.delay()

    def _check_eligibility(self, cycle, beneficiaries=None, offset=0, limit=None, do_count=False):
        if beneficiaries is None:
            beneficiaries = cycle.get_beneficiaries(
                ["draft", "enrolled", "not_eligible"],
                offset=offset,
                limit=limit,
                order="id",
            )

        eligibility_managers = cycle.program_id.get_managers(constants.MANAGER_ELIGIBILITY)
        filtered_beneficiaries = beneficiaries
        for manager in eligibility_managers:
            filtered_beneficiaries = manager.verify_cycle_eligibility(cycle, filtered_beneficiaries)

        filtered_beneficiaries.write({"state": "enrolled"})

        beneficiaries_ids = beneficiaries.ids
        filtered_beneficiaries_ids = filtered_beneficiaries.ids
        ids_to_remove = list(set(beneficiaries_ids) - set(filtered_beneficiaries_ids))

        # Mark the beneficiaries as not eligible
        memberships_to_remove = self.env["spp.cycle.membership"].browse(ids_to_remove)
        memberships_to_remove.write({"state": "not_eligible"})

        # Disable the entitlements of the beneficiaries
        entitlements = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", cycle.id),
                ("partner_id", "in", memberships_to_remove.mapped("partner_id.id")),
            ]
        )
        entitlements.write({"state": "cancelled"})

        if do_count:
            # Compute Statistics
            cycle._compute_members_count()

        return len(filtered_beneficiaries)

    def prepare_entitlements(self, cycle):
        for rec in self:
            rec._ensure_can_edit_cycle(cycle)
            # Get all the enrolled beneficiaries
            beneficiaries_count = cycle.get_beneficiaries(["enrolled"], count=True)
            rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if beneficiaries_count < self.MIN_ROW_JOB_QUEUE:
                self._prepare_entitlements(cycle, do_count=True)
                # No return action - let Odoo refresh the view automatically
            else:
                self._prepare_entitlements_async(cycle, beneficiaries_count)

    def _prepare_entitlements_async(self, cycle, beneficiaries_count):
        _logger.debug("Prepare entitlement asynchronously")
        cycle.message_post(body=_("Prepare entitlement for %s beneficiaries started.", beneficiaries_count))
        cycle.write(
            {
                "is_locked": True,
                "locked_reason": _("Prepare entitlement for beneficiaries."),
            }
        )

        jobs = []
        for i in range(0, beneficiaries_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(self.delayable(channel="cycle")._prepare_entitlements(cycle, i, self.MAX_ROW_JOB_QUEUE))
        main_job = group(*jobs)
        main_job.on_done(
            self.delayable(channel="cycle").mark_prepare_entitlement_as_done(cycle, _("Entitlement Ready."))
        )
        main_job.delay()

    def _prepare_entitlements(self, cycle, offset=0, limit=None, do_count=False):
        """Prepare Entitlements
        Get the beneficiaries and generate their entitlements.

        :param cycle: The cycle
        :param offset: Optional integer value for the ORM search offset
        :param limit: Optional integer value for the ORM search limit
        :param do_count: Boolean - set to False to not run compute function
        :return:
        """
        beneficiaries = cycle.get_beneficiaries(["enrolled"], offset=offset, limit=limit, order="id")
        ent_manager = self.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
        if not ent_manager:
            raise UserError(_("No Entitlement Manager defined."))
        ent_manager.prepare_entitlements(cycle, beneficiaries)

        if do_count:
            # Update Statistics
            cycle._compute_entitlements_count()

    def mark_distributed(self, cycle):
        cycle.update({"state": constants.STATE_DISTRIBUTED})

    def mark_ended(self, cycle):
        cycle.update({"state": constants.STATE_ENDED})

    def mark_cancelled(self, cycle):
        cycle.update({"state": constants.STATE_CANCELLED})

    def new_cycle(self, name, new_start_date, sequence):
        _logger.debug("Creating new cycle for program ID %s", self.program_id.id)
        _logger.debug("New start date: %s", new_start_date)

        # convert date to datetime
        new_start_date = datetime.combine(new_start_date, datetime.min.time())

        # Check if we need custom month-end handling
        # For monthly recurrence with day > 28, we use custom logic to handle
        # months with fewer days (e.g., February)
        if self._needs_month_end_fallback():
            start_date, end_date = self._calculate_cycle_dates_with_fallback(new_start_date)
        else:
            # Use standard rrule-based calculation
            start_date, end_date = self._calculate_cycle_dates_standard(new_start_date)

        for rec in self:
            cycle = self.env["spp.cycle"].create(
                {
                    "program_id": rec.program_id.id,
                    "name": name,
                    "state": "draft",
                    "sequence": sequence,
                    "start_date": start_date,
                    "end_date": end_date,
                    "auto_approve_entitlements": rec.auto_approve_entitlements,
                }
            )
            _logger.debug("New cycle created: ID %s", cycle.id)
            return cycle

    def _needs_month_end_fallback(self):
        """Check if we need custom month-end date handling.

        Returns True for monthly recurrence with day > 28, which may not exist
        in all months (e.g., Feb 30 doesn't exist).
        """
        return self.rrule_type == "monthly" and self.month_by == "date" and self.day and self.day > 28

    def _get_safe_day_for_month(self, year, month, target_day):
        """Get the actual day to use for a given month, clamping to the last day if needed.

        Args:
            year: The year
            month: The month (1-12)
            target_day: The desired day of month

        Returns:
            The actual day to use (may be less than target_day for short months)
        """
        last_day_of_month = calendar.monthrange(year, month)[1]
        return min(target_day, last_day_of_month)

    def _calculate_cycle_dates_with_fallback(self, new_start_date):
        """Calculate cycle start and end dates with month-end fallback logic.

        For months that don't have the configured day (e.g., February with day=30),
        this uses the last available day of the month instead.

        Args:
            new_start_date: The requested start date for the cycle

        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        target_day = self.day
        interval = self.interval or self.cycle_duration or 1

        # Find the appropriate start date
        year = new_start_date.year
        month = new_start_date.month

        # Get the safe day for the current month
        safe_day = self._get_safe_day_for_month(year, month, target_day)
        start_date = datetime(year, month, safe_day, 11, 0, 0)

        # If the calculated start_date is before new_start_date, move to next interval
        if start_date < new_start_date:
            # Move forward by the interval
            next_date = start_date + relativedelta(months=interval)
            safe_day = self._get_safe_day_for_month(next_date.year, next_date.month, target_day)
            start_date = datetime(next_date.year, next_date.month, safe_day, 11, 0, 0)

        # Calculate end date (one day before next cycle start)
        next_cycle_date = start_date + relativedelta(months=interval)
        next_safe_day = self._get_safe_day_for_month(next_cycle_date.year, next_cycle_date.month, target_day)
        next_cycle_start = datetime(next_cycle_date.year, next_cycle_date.month, next_safe_day, 11, 0, 0)
        end_date = next_cycle_start - timedelta(days=1)

        _logger.debug(
            "Month-end fallback: target_day=%d, start=%s, end=%s",
            target_day,
            start_date.date(),
            end_date.date(),
        )

        return start_date, end_date

    def _calculate_cycle_dates_standard(self, new_start_date):
        """Calculate cycle dates using standard rrule-based logic.

        Args:
            new_start_date: The requested start date for the cycle

        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        # get start date and end date
        # Note:
        # second argument is irrelevant but make sure it is in timedelta class
        # and do not exceed to 24 hours
        occurences = self._get_ranges(new_start_date, timedelta(seconds=1))

        prev_occurence = next(occurences)
        current_occurence = next(occurences)

        start_date = None
        end_date = None

        # This prevents getting an end date that is less than the start date
        while True:
            # get the date of occurences
            start_date = prev_occurence[0]
            end_date = current_occurence[0] - timedelta(days=1)

            # To handle DST (Daylight Saving Time) changes
            start_date = start_date + timedelta(hours=11)
            end_date = end_date + timedelta(hours=11)

            if start_date >= new_start_date:
                break

            # move current occurence to previous then get a new current occurence
            prev_occurence = current_occurence
            current_occurence = next(occurences)

        return start_date, end_date

    def copy_beneficiaries_from_program(self, cycle, state="enrolled"):
        self._ensure_can_edit_cycle(cycle)
        self.ensure_one()

        for rec in self:
            beneficiary_ids = rec.program_id.get_beneficiaries(["enrolled"]).mapped("partner_id.id")
            return rec.add_beneficiaries(cycle, beneficiary_ids, state)

    def add_beneficiaries(self, cycle, beneficiaries, state="draft"):
        """
        Add beneficiaries to the cycle
        """
        self.ensure_one()
        self._ensure_can_edit_cycle(cycle)
        _logger.debug("Adding beneficiaries to the cycle ID %s", cycle.id)
        _logger.debug("Beneficiaries: %s", len(beneficiaries))

        # Only add beneficiaries not added yet
        existing_ids = cycle.cycle_membership_ids.mapped("partner_id.id")
        _logger.debug("Existing IDs: %s", len(existing_ids))
        beneficiaries = list(set(beneficiaries) - set(existing_ids))
        if len(beneficiaries) == 0:
            message = _("No beneficiaries to import.")
            kind = "warning"
            sticky = False
        elif len(beneficiaries) < self.MIN_ROW_JOB_QUEUE:
            self._add_beneficiaries(cycle, beneficiaries, state, do_count=True)
            message = _("%s beneficiaries imported.", len(beneficiaries))
            kind = "success"
            sticky = False
        else:
            self._add_beneficiaries_async(cycle, beneficiaries, state)
            message = _("Import of %s beneficiaries started.", len(beneficiaries))
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

    def _add_beneficiaries_async(self, cycle, beneficiaries, state):
        _logger.debug("Adding beneficiaries asynchronously")
        cycle.message_post(body=f"Import of {len(beneficiaries)} beneficiaries started.")
        cycle.write({"is_locked": True, "locked_reason": _("Importing beneficiaries.")})

        beneficiaries_count = len(beneficiaries)
        jobs = []
        for i in range(0, beneficiaries_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(
                self.delayable(channel="cycle")._add_beneficiaries(
                    cycle,
                    beneficiaries[i : i + self.MAX_ROW_JOB_QUEUE],
                    state,
                )
            )

        main_job = group(*jobs)
        main_job.on_done(self.delayable(channel="cycle").mark_import_as_done(cycle, _("Beneficiary import finished.")))
        main_job.delay()

    def _add_beneficiaries(self, cycle, beneficiaries, state="draft", do_count=False):
        """Add Beneficiaries

        :param cycle: Recordset of cycle
        :param beneficiaries: List of partner IDs
        :param state: String state to be set to beneficiary
        :param do_count: Boolean - set to False to not run compute functions
        """
        today = fields.Date.today()
        vals_list = [
            {
                "partner_id": partner_id,
                "cycle_id": cycle.id,
                "enrollment_date": today,
                "state": state,
            }
            for partner_id in beneficiaries
        ]
        self.env["spp.cycle.membership"].bulk_create_memberships(vals_list, skip_duplicates=True)

        # Raw SQL bypasses the ORM cache — invalidate so subsequent reads
        # (e.g. cycle.cycle_membership_ids) reflect the new rows.
        cycle.invalidate_recordset(["cycle_membership_ids"])

        if do_count:
            # Update Statistics
            cycle._compute_members_count()

    @api.depends("cycle_duration")
    def _compute_interval(self):
        for rec in self:
            rec.interval = rec.cycle_duration
