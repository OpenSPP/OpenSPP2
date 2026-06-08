# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.job_worker.delay import group

_logger = logging.getLogger(__name__)


class EntitlementManager(models.Model):
    _name = "spp.program.entitlement.manager"
    _description = "Entitlement Manager"
    _inherit = "spp.manager.mixin"

    program_id = fields.Many2one("spp.program", "Program", ondelete="cascade")

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = ("spp.program.entitlement.manager.default", "Default")
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class BaseEntitlementManager(models.AbstractModel):
    _name = "spp.base.program.entitlement.manager"
    _inherit = "spp.base.programs.manager"
    _description = "Base Entitlement Manager"

    IS_CASH_ENTITLEMENT = True
    MIN_ROW_JOB_QUEUE = 200
    MAX_ROW_JOB_QUEUE = 2000

    name = fields.Char("Manager Name", required=True)
    program_id = fields.Many2one("spp.program", string="Program", required=True)
    approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Approval Definition",
        copy=True,
        domain="[('model_id.model', '=', 'spp.entitlement')]",
    )

    def prepare_entitlements(self, cycle, beneficiaries):
        """
        This method is used to prepare the entitlement list of the beneficiaries.
        :param cycle: The cycle.
        :param beneficiaries: The beneficiaries.
        :return entitlements:
        """
        raise NotImplementedError()

    def set_pending_validation_entitlements(self, cycle):
        """Base Entitlement Manager :meth:`set_pending_validate_entitlements`
        Set entitlements to pending_validation in a cycle
        Override in entitlement manager

        :param cycle: A recordset of cycle
        :return:
        """
        raise NotImplementedError()

    def _set_pending_validation_entitlements_async(self, cycle, entitlements):
        """Set Entitlements to Pending Validation
        Base Entitlement Manager :meth:`_set_pending_validation_entitlements_async`
        Asynchronous setting of entitlements to pending_validation in a cycle using `job_queue`

        :param cycle: A recordset of cycle
        :param entitlements: A recordset of entitlements to process
        :return:
        """
        entitlements_count = len(entitlements)
        _logger.debug("Set entitlements to pending validation asynchronously")
        cycle.message_post(
            body=_(
                "Setting %s entitlements to pending validation has started.",
                entitlements_count,
            )
        )
        cycle.write(
            {
                "is_locked": True,
                "locked_reason": _("Set entitlements to pending validation for cycle."),
            }
        )

        jobs = []
        for i in range(0, entitlements_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(
                self.delayable(channel="entitlement_approval")._set_pending_validation_entitlements(
                    entitlements[i : i + self.MAX_ROW_JOB_QUEUE]
                )
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable().mark_job_as_done(cycle, _("Entitlements Set to Pending Validation.")))
        main_job.on_error(
            self.delayable().mark_job_as_failed(cycle, _("Setting entitlements to pending validation failed."))
        )
        main_job.delay()

    def _set_pending_validation_entitlements(self, entitlements):
        """
        Base Entitlement Manager :meth:`_set_pending_validation_entitlements`
        Synchronous setting of entitlements to pending_validation in a cycle
        Override in entitlement manager

        :param entitlements: A recordset of entitlements
        :return:
        """
        raise NotImplementedError()

    def validate_entitlements(self, cycle):
        """Base Entitlement Manager :meth:`validate_entitlements`
        Validate entitlements for a cycle
        Override in entitlement manager

        :param cycle: A recordset of cycle
        :return:
        """
        raise NotImplementedError()

    def _validate_entitlements_async(self, cycle, entitlements, entitlements_count):
        """Validate Entitlements
        Base Entitlement Manager :meth:`_validate_entitlements_async`
        Asynchronous validation of entitlements in a cycle using `job_queue`

        :param cycle: A recordset of cycle
        :param entitlements: A recordset of entitlements to validate
        :param entitlements_count: Integer count of entitlements to validate
        :return:
        """
        _logger.debug("Validate entitlements asynchronously")
        cycle.message_post(body=_("Validate %s entitlements started.", entitlements_count))
        cycle.write(
            {
                "is_locked": True,
                "locked_reason": _("Validate and approve entitlements for cycle."),
            }
        )

        jobs = []
        for i in range(0, entitlements_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(
                self.delayable(channel="entitlement_approval")._validate_entitlements(
                    entitlements[i : i + self.MAX_ROW_JOB_QUEUE]
                )
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable().mark_job_as_done(cycle, _("Entitlements Validated and Approved.")))
        main_job.on_error(
            self.delayable().mark_job_as_failed(cycle, _("Validation and approval of entitlements failed."))
        )
        main_job.delay()

    def _validate_entitlements(self, entitlements):
        """
        Base Entitlement Manager :meth:`_validate_entitlements`
        Synchronous validation of entitlements in a cycle
        Override in entitlement manager

        :param entitlements: A recordset of entitlements to validate
        :return:
        """
        # Call the program's entitlement manager and validate the entitlements
        # TODO: Use a Job attached to the cycle
        # TODO: Implement validation workflow
        raise NotImplementedError()

    def approve_entitlements(self, entitlements):
        """Base Entitlement Manager :meth:`_approve_entitlements`
        Approve selected entitlements
        Override in entitlement manager

        :param entitlements: Selected entitlements to approve.
        :return:
        """
        raise NotImplementedError()

    def cancel_entitlements(self, cycle):
        """Base Entitlement Manager :meth:`cancel_entitlements`
        Cancel entitlements in a cycle
        Override in entitlement manager

        :param cycle: A recordset of cycle
        :return:
        """
        raise NotImplementedError()

    def _cancel_entitlements_async(self, cycle, entitlements, entitlements_count):
        """Cancel Entitlements
        Base Entitlement Manager :meth:`_cancel_entitlements_async`
        Asynchronous cancellation of entitlements in a cycle using `job_queue`

        :param cycle: A recordset of cycle
        :param entitlements: A recordset of entitlements to cancel
        :param entitlements_count: Integer value of total entitlements to process
        :return:
        """
        _logger.debug("Cancel entitlements asynchronously")
        cycle.message_post(body=_("Cancel %s entitlements started.", entitlements_count))
        cycle.write(
            {
                "is_locked": True,
                "locked_reason": _("Cancel entitlements for cycle."),
            }
        )

        jobs = []
        for i in range(0, entitlements_count, self.MAX_ROW_JOB_QUEUE):
            jobs.append(
                self.delayable(channel="entitlement_approval")._cancel_entitlements(
                    entitlements[i : i + self.MAX_ROW_JOB_QUEUE]
                )
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable().mark_job_as_done(cycle, _("Entitlements Cancelled.")))
        main_job.on_error(self.delayable().mark_job_as_failed(cycle, _("Cancelling entitlements failed.")))
        main_job.delay()

    def _cancel_entitlements(self, entitlements):
        """
        Base Entitlement Manager :meth:`_cancel_entitlements`
        Synchronous cancellation of entitlements in a cycle
        Override in entitlement manager

        :param entitlements: A recordset of entitlements to cancel
        :return:
        """
        raise NotImplementedError()

    def mark_job_as_done(self, cycle, msg):
        """
        Base :meth:`mark_job_as_done`
        Post a message in the chatter

        :param cycle: A recordset of cycle
        :param msg: A string to be posted in the chatter
        :return:
        """
        self.ensure_one()
        # Clear the lock first so a chatter-side failure can't leave the
        # cycle stuck with "Operation in progress".
        cycle.write({"is_locked": False, "locked_reason": False})
        try:
            cycle.message_post(body=msg)
        except Exception:
            _logger.exception("Failed to post completion chatter on cycle %s", cycle.id)

    def mark_job_as_failed(self, cycle, msg):
        """Run via on_error() when the async pipeline fails.

        Clears the cycle lock and posts a failure note to chatter so the
        user understands the operation finished without success — instead
        of the lock remaining set indefinitely (the bug this fix targets).

        :param cycle: A recordset of cycle
        :param msg: A string to be posted in the chatter
        """
        self.ensure_one()
        cycle.write({"is_locked": False, "locked_reason": False})
        try:
            cycle.message_post(body=msg)
        except Exception:
            _logger.exception("Failed to post failure chatter on cycle %s", cycle.id)

    def open_entitlements_form(self, cycle):
        """
        This method is used to open the list view of entitlements in a cycle.
        :param cycle: The cycle.
        :return:
        """
        raise NotImplementedError()

    def open_entitlement_form(self, rec):
        """
        This method is used to open the form view of a selected entitlement.
        :param rec: The entitlement.
        :return:
        """
        raise NotImplementedError()

    def check_fund_balance(self, program_id):
        company_id = self.env.user.company_id and self.env.user.company_id.id or None
        retval = 0.0
        if company_id:
            params = (
                company_id,
                program_id,
            )

            # Get the current fund balance
            fund_bal = 0.0
            sql = """
                select sum(amount) as total_fund
                from spp_program_fund
                where company_id = %s
                    AND program_id = %s
                    AND state = 'posted'
                """
            self._cr.execute(sql, params)
            program_funds = self._cr.dictfetchall()
            fund_bal = program_funds[0]["total_fund"] or 0.0

            # Get the current entitlement totals
            total_entitlements = 0.0
            sql = """
                select sum(a.initial_amount) as total_entitlement
                from spp_entitlement a
                    left join spp_cycle b on b.id = a.cycle_id
                where a.company_id = %s
                    AND b.program_id = %s
                    AND a.state = 'approved'
                """
            self._cr.execute(sql, params)
            entitlements = self._cr.dictfetchall()
            total_entitlements = entitlements[0]["total_entitlement"] or 0.0

            retval = fund_bal - total_entitlements
        return retval


class DefaultCashEntitlementManager(models.Model):
    _name = "spp.program.entitlement.manager.default"
    _inherit = ["spp.base.program.entitlement.manager", "spp.manager.source.mixin"]
    _description = "Default Entitlement Manager"

    # Set to True so that the UI will display the payment management components
    IS_CASH_ENTITLEMENT = True

    amount_per_cycle = fields.Monetary(
        currency_field="currency_id",
        aggregator="sum",
        default=0.0,
    )
    amount_per_individual_in_group = fields.Monetary(
        currency_field="currency_id",
        aggregator="sum",
        default=0.0,
    )
    max_individual_in_group = fields.Integer(
        default=0,
        string="Maximum number of individual in group",
        help="0 means no limit",
    )

    currency_id = fields.Many2one("res.currency", related="program_id.journal_id.currency_id", readonly=True)

    # Transfer Fees
    transfer_fee_pct = fields.Float(
        "Transfer Fee(%)",
        digits=(5, 2),
        default=0.0,
        help="Transfer fee will be a percentage of amount",
    )
    transfer_fee_amount = fields.Monetary(
        "Transfer Fee Amount",
        default=0.0,
        currency_field="currency_id",
        help="Set fixed transfer fee amount",
    )

    # Alias for compatibility with wizards/tests expecting `transfer_fee_amt`
    # Note: This is a related field to transfer_fee_amount and inherits its label
    transfer_fee_amt = fields.Monetary(
        related="transfer_fee_amount",
        currency_field="currency_id",
        readonly=False,
        store=True,
    )

    # Group able to validate the payment
    # Todo: Create a record rule for payment_validation_group
    entitlement_validation_group_id = fields.Many2one("res.groups", string="Entitlement Validation Group")

    @api.onchange("transfer_fee_pct")
    def on_transfer_fee_pct_change(self):
        if self.transfer_fee_pct > 0.0:
            self.transfer_fee_amount = 0.0

    @api.onchange("transfer_fee_amount")
    def on_transfer_fee_amount_change(self):
        if self.transfer_fee_amount > 0.0:
            self.transfer_fee_pct = 0.0

    def prepare_entitlements(self, cycle, beneficiaries):
        """Prepare entitlements.
        This method is used to prepare the entitlement list of the beneficiaries.
        :param cycle: The cycle.
        :param beneficiaries: The beneficiaries.
        :return entitlements:
        """
        benecifiaries_ids = beneficiaries.mapped("partner_id.id")

        benecifiaries_with_entitlements = (
            self.env["spp.entitlement"]
            .search([("cycle_id", "=", cycle.id), ("partner_id", "in", benecifiaries_ids)])
            .mapped("partner_id.id")
        )
        entitlements_to_create = [
            benecifiaries_id
            for benecifiaries_id in benecifiaries_ids
            if benecifiaries_id not in benecifiaries_with_entitlements
        ]

        entitlement_start_validity = cycle.start_date
        entitlement_end_validity = cycle.end_date
        entitlement_currency = self.currency_id.id

        beneficiaries_with_entitlements_to_create = self.env["res.partner"].browse(entitlements_to_create)

        individual_count = beneficiaries_with_entitlements_to_create.count_individuals()
        individual_count_map = dict(individual_count)

        entitlements = []
        for beneficiary_id in beneficiaries_with_entitlements_to_create:
            amount = self._calculate_amount(beneficiary_id, individual_count_map.get(beneficiary_id.id, 0))
            transfer_fee = 0.0
            if self.transfer_fee_pct > 0.0:
                transfer_fee = amount * (self.transfer_fee_pct / 100.0)
            elif self.transfer_fee_amount > 0.0:
                transfer_fee = self.transfer_fee_amount
            entitlements.append(
                {
                    "cycle_id": cycle.id,
                    "partner_id": beneficiary_id.id,
                    "initial_amount": amount,
                    "transfer_fee": transfer_fee,
                    "currency_id": entitlement_currency,
                    "state": "draft",
                    "is_cash_entitlement": True,
                    "valid_from": entitlement_start_validity,
                    "valid_until": entitlement_end_validity,
                }
            )
        if entitlements:
            return self.env["spp.entitlement"].create(entitlements)
        return None

    def set_pending_validation_entitlements(self, cycle):
        """Set entitlements to pending validation.
        Default Entitlement Manager :meth:`set_pending_validation_entitlements`
        Set entitlements to pending_validation in a cycle

        :param cycle: A recordset of cycle
        :return:
        """
        # Get the number of entitlements in cycle
        entitlements = cycle.get_entitlements(
            ["draft"],
            entitlement_model="spp.entitlement",
        )
        entitlements_count = len(entitlements)
        if entitlements_count < self.MIN_ROW_JOB_QUEUE:
            self._set_pending_validation_entitlements(entitlements)

        else:
            self._set_pending_validation_entitlements_async(cycle, entitlements)

    def _set_pending_validation_entitlements(self, entitlements):
        """Set entitlements to pending validation.
        Default Entitlement Manager :meth:`_set_pending_validation_entitlements`
        Synchronous setting of entitlements to pending_validation in a cycle

        :param entitlements: A recordset of entitlements
        :return:
        """
        if not self.approval_definition_id:
            raise ValidationError(_("The entitlement approval definition is not specified!"))
        else:
            entitlements.action_submit_for_approval()

    def validate_entitlements(self, cycle):
        """Validate entitlements.
        Default Entitlement Manager :meth:`validate_entitlements`
        Validate entitlements in a cycle

        :param cycle: A recordset of cycle
        :return:
        """
        # Get the number of entitlements in cycle
        entitlements = cycle.get_entitlements(
            ["draft", "pending_validation"],
            entitlement_model="spp.entitlement",
        )
        entitlements_count = len(entitlements)
        if entitlements_count < self.MIN_ROW_JOB_QUEUE:
            err, message = self._validate_entitlements(entitlements)
            if err > 0:
                kind = "danger"
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Entitlement"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }
            else:
                kind = "success"
                approved_entitlements_count = len(entitlements) - err  # Calculate the approved count
                if err != 0:
                    message = _(
                        f"{approved_entitlements_count} Entitlements are successfully approved and"
                        f"{err} are not approved."
                    )
                else:
                    message = _(f"{approved_entitlements_count} Entitlements are successfully approved.")

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Entitlement"),
                        "message": message,
                        "sticky": True,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }
        else:
            self._validate_entitlements_async(cycle, entitlements, entitlements_count)

    def _validate_entitlements(self, entitlements):
        """Validate entitlements.
        Default Entitlement Manager :meth:`_validate_entitlements`
        Synchronous validation of entitlements in a cycle

        :param entitlements: A recordset of entitlements to validate
        :return err: Integer number of errors
        :return message: String description of the error
        """
        err, message = self.approve_entitlements(entitlements)
        return err, message

    def cancel_entitlements(self, cycle):
        """
        Default Entitlement Manager :meth:`cancel_entitlements`
        Cancel entitlements in a cycle

        :param cycle: A recordset of cycle
        :return:
        """
        # Get the number of entitlements in cycle
        entitlements = cycle.get_entitlements(
            ["draft", "pending_validation", "approved"],
            entitlement_model="spp.entitlement",
        )
        entitlements_count = len(entitlements)
        if entitlements_count < self.MIN_ROW_JOB_QUEUE:
            self._cancel_entitlements(entitlements)
        else:
            self._cancel_entitlements_async(cycle, entitlements, entitlements_count)

    def _cancel_entitlements(self, entitlements):
        """
        Default Entitlement Manager :meth:`_cancel_entitlements`
        Synchronous cancellation of entitlements in a cycle

        :param entitlements: A recordset of entitlements to cancel
        :return:
        """
        entitlements.update({"state": "cancelled"})

    def _calculate_amount(self, beneficiary, num_individuals):
        total = self.amount_per_cycle
        if beneficiary.is_group:
            if num_individuals:
                if self.max_individual_in_group:
                    num_individuals = min(num_individuals, self.max_individual_in_group)

                total += self.amount_per_individual_in_group * float(num_individuals)
        return total

    def approve_entitlements(self, entitlements):
        """Approve entitlements.
        Default Entitlement Manager :meth:`approve_entitlements`
        Approve selected entitlements

        :param entitlements: Selected entitlements to approve
        :return state_err: Integer number of errors
        :return message: String description of the errors
        """
        amt = 0.0
        # Odoo 19's account.payment expects an "outstanding" account; ensure one exists for the company
        company = self.env.company
        if not company.transfer_account_id:
            outstanding_account = self.env["account.account"].create(
                {
                    "name": "Outstanding Payments",
                    "code": "OUTPAY",
                    "account_type": "liability_current",
                    "company_ids": (
                        [(6, 0, [company.id])] if "company_ids" in self.env["account.account"]._fields else False
                    ),
                    "reconcile": True,
                }
            )
            company.transfer_account_id = outstanding_account.id

        state_err = 0
        message = ""
        sw = 0

        # Prefetch related fields to avoid N+1 queries in loop
        entitlements.mapped("cycle_id.program_id")
        entitlements.mapped("partner_id")
        entitlements.mapped("journal_id.currency_id")

        # Fetch fund balance once for the whole batch instead of per entitlement
        fund_balance = self.check_fund_balance(entitlements[0].cycle_id.program_id.id)

        for rec in entitlements:
            if rec.state in ("draft", "pending_validation"):
                remaining_balance = fund_balance - amt
                if remaining_balance >= rec.initial_amount:
                    amt += rec.initial_amount
                    # Prepare journal entry (account.move) via account.payment
                    amount = rec.initial_amount
                    new_service_fee = None
                    if rec.transfer_fee > 0.0:
                        amount -= rec.transfer_fee
                        # Incurred Fees (transfer fees)
                        payment = {
                            "partner_id": rec.partner_id.id,
                            "payment_type": "outbound",
                            "amount": rec.transfer_fee,
                            "currency_id": rec.journal_id.currency_id.id,
                            "journal_id": rec.journal_id.id,
                            "partner_type": "supplier",
                            "payment_reference": f"Service Fee: Code: {rec.code}",
                            "destination_account_id": rec.partner_id.property_account_payable_id.id,
                        }
                        new_service_fee = self.env["account.payment"].create(payment)

                    # Fund Disbursed (amount - transfer fees)
                    payment = {
                        "partner_id": rec.partner_id.id,
                        "payment_type": "outbound",
                        "amount": amount,
                        "currency_id": rec.journal_id.currency_id.id,
                        "journal_id": rec.journal_id.id,
                        "partner_type": "supplier",
                        "payment_reference": f"Fund disbursed to beneficiary: Code: {rec.code}",
                        "destination_account_id": rec.partner_id.property_account_payable_id.id,
                    }
                    new_payment = self.env["account.payment"].create(payment)

                    # Use the approval mixin's method to properly set all audit fields
                    if hasattr(rec, "_do_approve"):
                        rec._do_approve(auto=True)

                    # Update entitlement-specific fields
                    rec.update(
                        {
                            "disbursement_id": new_payment.id,
                            "service_fee_disbursement_id": new_service_fee and new_service_fee.id or None,
                            "state": "approved",
                            "date_approved": fields.Date.today(),
                        }
                    )
                    # Force recompute of approval_state
                    rec._compute_approval_state()
                else:
                    message = _(
                        "The fund for the program: %(program)s [%(fund).2f] "
                        + "is insufficient for the entitlement: %(entitlement)s"
                    ) % {
                        "program": rec.cycle_id.program_id.name,
                        "fund": remaining_balance,
                        "entitlement": rec.code,
                    }
                    # Stop the process and return an error
                    return (1, message)
            else:
                state_err += 1
                if sw == 0:
                    sw = 1
                    message = _("Entitlement State Error! Entitlements not in 'pending validation' state:\n")
                message += _("Program: %(prg)s, Beneficiary: %(partner)s.\n") % {
                    "prg": rec.cycle_id.program_id.name,
                    "partner": rec.partner_id.name,
                }

        return (state_err, message)

    def open_entitlements_form(self, cycle):
        # self.ensure_one()
        action = {
            "name": _("Cycle Entitlements"),
            "type": "ir.actions.act_window",
            "res_model": "spp.entitlement",
            "context": {
                "create": False,
                "default_cycle_id": cycle.id,
                # "search_default_approved_state": 1,
            },
            "view_mode": "list,form",
            "views": [
                [self.env.ref("spp_programs.view_entitlement_tree").id, "list"],
                [self.env.ref("spp_programs.view_entitlement_form").id, "form"],
            ],
            "domain": [("cycle_id", "=", cycle.id)],
        }
        return action

    def open_entitlement_form(self, rec):
        return {
            "name": "Entitlement",
            "view_mode": "form",
            "res_model": "spp.entitlement",
            "res_id": rec.id,
            "view_id": self.env.ref("spp_programs.view_entitlement_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    @api.model
    def _group_entitlements_by_cycle(self, entitlements):
        cycles = set(map(lambda x: x.cycle_id, entitlements))
        cycle_entitlements = [entitlements.filtered_domain([("cycle_id", "=", cycle.id)]) for cycle in cycles]
        return cycles, cycle_entitlements
