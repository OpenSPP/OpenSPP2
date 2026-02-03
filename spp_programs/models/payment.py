# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPPayment(models.Model):
    _name = "spp.payment"
    _description = "Payment"
    # _inherit = ["disable.edit.mixin"]
    _order = "id desc"

    # DISABLE_EDIT_DOMAIN = [("status", "=", "paid")]

    name = fields.Char("Internal Reference #", default=str(uuid4()), readonly=True, copy=False)
    entitlement_id = fields.Many2one("spp.entitlement", "Entitlement", required=True)
    cycle_id = fields.Many2one("spp.cycle", "Cycle", readonly=True)
    program_id = fields.Many2one("spp.program", related="cycle_id.program_id", readonly=True)
    partner_id = fields.Many2one(
        "res.partner",
        related="entitlement_id.partner_id",
        string="Beneficiary",
        readonly=True,
    )

    batch_id = fields.Many2one("spp.payment.batch", "Payment Batch")

    state = fields.Selection(
        selection=[
            ("issued", "Issued"),
            ("sent", "Sent"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        required=True,
        default="issued",
    )
    status = fields.Selection(
        selection=[
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        string="Payment Status",
    )
    is_status_final = fields.Boolean("Is final payment status", default=False)
    status_datetime = fields.Datetime()

    # We should have a snapshot of the account number from the beneficiary
    #  at the point of creating the payment
    account_number = fields.Char()

    amount_issued = fields.Monetary(required=True, currency_field="currency_id")
    amount_paid = fields.Monetary(currency_field="currency_id")
    issuance_date = fields.Datetime(default=fields.Datetime.now)  # Should default to Datetime.Now()
    payment_datetime = fields.Datetime()

    payment_fee = fields.Monetary(currency_field="currency_id")

    currency_id = fields.Many2one("res.currency", readonly=True, related="journal_id.currency_id")

    journal_id = fields.Many2one(
        "account.journal",
        "Program Journal",
        store=True,
        compute="_compute_journal_id",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("entitlement_id.cycle_id.program_id.journal_id")
    def _compute_journal_id(self):
        for record in self:
            record.journal_id = (
                record.entitlement_id
                and record.entitlement_id.cycle_id
                and record.entitlement_id.cycle_id.program_id
                and record.entitlement_id.cycle_id.program_id.journal_id
                and record.entitlement_id.cycle_id.program_id.journal_id.id
                or None
            )

    def check_account_status(self):
        # Checks if the account is available for payment
        # Simple implementation will check if a account number has been set
        pass

    def send_payment(self):
        pass

    def unlink(self):
        for record in self:
            if record.state != "issued":
                raise ValidationError(_(f"You cannot delete records in {record.status} state."))
        return super().unlink()


class SPPPaymentBatch(models.Model):
    _name = "spp.payment.batch"
    _description = "Payment Batch"
    _order = "id desc"

    name = fields.Char("Internal Batch Reference #", default=str(uuid4()), readonly=True, copy=False)
    cycle_id = fields.Many2one("spp.cycle", "Cycle", readonly=True)
    program_id = fields.Many2one("spp.program", related="cycle_id.program_id", string="Program", readonly=True)
    external_batch_ref = fields.Char("External Batch Reference #")

    has_batch_started = fields.Boolean()
    has_batch_completed = fields.Boolean()

    payment_ids = fields.Many2many("spp.payment", string="Payments")

    # This set of fields hold the current statistics of the payment batch
    # We store this so that we can display this information without calling the payment system
    stats_issued_transactions = fields.Integer("Issued Transaction Statistics", readonly=True)
    stats_issued_amount = fields.Float("Issued Amount Statistics", readonly=True)
    stats_sent_transactions = fields.Integer("Sent Transactions Statistics", readonly=True)
    stats_sent_amount = fields.Float("Sent Amount Statistics", readonly=True)
    stats_paid_transactions = fields.Integer("Paid Transactions Statistics", readonly=True)
    stats_paid_amount = fields.Float("Paid Amount Statistics", readonly=True)
    stats_failed_transactions = fields.Integer("Failed Transactions Statistics", readonly=True)
    stats_failed_amount = fields.Float("Failed Amount Statistics", readonly=True)

    stats_datetime = fields.Datetime("Statistics Date/Time")

    tag_id = fields.Many2one("spp.payment.batch.tag", string="Tag")

    def send_payment(self):
        # 1. Issue the payment of the beneficiaries using payment_manager.send_payments()
        return self.program_id.get_manager(self.program_id.MANAGER_PAYMENT).send_payments(self)

    def unlink(self):
        for record in self:
            if record.has_batch_started:
                raise ValidationError(_("Deletion is not allowed once the batch has started."))
            else:
                record.payment_ids.unlink()
        return super().unlink()


class SPPPaymentBatchTag(models.Model):
    _name = "spp.payment.batch.tag"
    _description = "Payment Batch Tag"
    _order = "order asc"

    name = fields.Char()

    order = fields.Integer()

    domain = fields.Text(default="[]")

    max_batch_size = fields.Integer(default=500)
