# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import calendar
import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class EntitlementSchedule(models.Model):
    """Full benefit schedule for one enrolled child.

    The schedule is generated once, up front, for the whole benefit period
    (birth month through the month the child reaches the age limit) and acts
    as the source of truth for entitlement amounts. Cycle-time entitlement
    preparation materializes schedule lines into standard entitlements
    instead of computing amounts on the fly.
    """

    _name = "spp.entitlement.schedule"
    _description = "Entitlement Schedule"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _rec_name = "display_name"

    partner_id = fields.Many2one(
        "res.partner",
        string="Beneficiary",
        required=True,
        index=True,
        domain=[("is_registrant", "=", True), ("is_group", "=", False)],
    )
    program_id = fields.Many2one("spp.program", string="Program", required=True, index=True)
    state = fields.Selection(
        selection=[("draft", "Draft"), ("active", "Active"), ("superseded", "Superseded")],
        default="draft",
        required=True,
        tracking=True,
    )
    date_of_birth = fields.Date(
        required=True,
        help="Date of birth the schedule was generated from (snapshot).",
    )
    monthly_amount = fields.Float(required=True)
    age_limit_months = fields.Integer(required=True, default=36)
    cutoff_day = fields.Integer(
        required=True,
        default=15,
        help="Day-of-month proration cut-off: born on or before this day gives a "
        "full entry month and a prorated exit month; born after it gives a "
        "prorated entry month and a full exit month.",
    )
    benefit_end_date = fields.Date(
        compute="_compute_benefit_end_date",
        store=True,
        help="Date the child attains the age limit.",
    )
    line_ids = fields.One2many("spp.entitlement.schedule.line", "schedule_id", string="Installments")
    line_count = fields.Integer(compute="_compute_line_stats")
    total_amount = fields.Float(compute="_compute_line_stats")

    @api.constrains("state", "partner_id", "program_id")
    def _check_single_active_schedule(self):
        for rec in self.filtered(lambda r: r.state == "active"):
            duplicate = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("partner_id", "=", rec.partner_id.id),
                    ("program_id", "=", rec.program_id.id),
                    ("state", "=", "active"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(_("A beneficiary can only have one active schedule per program."))

    @api.depends("partner_id", "program_id", "state")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("Schedule %(partner)s / %(program)s") % {
                "partner": rec.partner_id.name or "?",
                "program": rec.program_id.name or "?",
            }

    @api.depends("date_of_birth", "age_limit_months")
    def _compute_benefit_end_date(self):
        for rec in self:
            rec.benefit_end_date = (
                rec.date_of_birth + relativedelta(months=rec.age_limit_months) if rec.date_of_birth else False
            )

    @api.depends("line_ids", "line_ids.amount")
    def _compute_line_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.total_amount = sum(rec.line_ids.mapped("amount"))

    # ------------------------------------------------------------------
    # Schedule math
    # ------------------------------------------------------------------
    @api.model
    def _daily_rate(self, monthly_amount, year, month):
        return round(monthly_amount / calendar.monthrange(year, month)[1], 2)

    @api.model
    def _compute_schedule_lines(self, birthdate, monthly_amount, age_limit_months, cutoff_day):
        """Compute the full installment table for one child. Pure function.

        Returns a list of dicts: benefit_month (first of month), payable_from,
        payable_to, days_payable, daily_rate, proration (none/entry/exit), amount.

        Invariants enforced (validation errors, never silent):
        - a schedule is never prorated in both the entry and the exit month;
        - no installment exceeds the full monthly amount.
        """
        if not birthdate:
            raise ValidationError(_("A date of birth is required to generate a schedule."))
        if not monthly_amount or monthly_amount <= 0:
            raise ValidationError(_("The monthly benefit amount must be positive."))
        if not age_limit_months or age_limit_months <= 0:
            raise ValidationError(_("The benefit age limit must be positive."))

        end_date = birthdate + relativedelta(months=age_limit_months)
        entry_full = birthdate.day <= cutoff_day

        lines = []
        month_start = date(birthdate.year, birthdate.month, 1)
        while month_start <= end_date:
            days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
            month_end = date(month_start.year, month_start.month, days_in_month)
            is_entry = (month_start.year, month_start.month) == (birthdate.year, birthdate.month)
            is_exit = (month_start.year, month_start.month) == (end_date.year, end_date.month)

            proration = "none"
            payable_from, payable_to = month_start, month_end
            days_payable = days_in_month
            daily_rate = self._daily_rate(monthly_amount, month_start.year, month_start.month)
            amount = monthly_amount

            if is_entry and not entry_full:
                # Born after the cut-off: pay the days remaining in the birth
                # month, including the date of birth.
                proration = "entry"
                payable_from = birthdate
                days_payable = days_in_month - birthdate.day + 1
                amount = round(days_payable * daily_rate, 2)
            elif is_exit and entry_full:
                # Full entry month: the final month is prorated up to and
                # including the date the child attains the age limit.
                proration = "exit"
                payable_to = end_date
                days_payable = end_date.day
                amount = round(days_payable * daily_rate, 2)

            if amount > monthly_amount:
                raise ValidationError(
                    _("Installment for %(month)s exceeds the monthly amount.") % {"month": month_start}
                )
            lines.append(
                {
                    "benefit_month": month_start,
                    "payable_from": payable_from,
                    "payable_to": payable_to,
                    "days_payable": days_payable,
                    "daily_rate": daily_rate,
                    "proration": proration,
                    "amount": amount,
                }
            )
            month_start = month_start + relativedelta(months=1)

        prorated = [line for line in lines if line["proration"] != "none"]
        if len(prorated) > 1:
            raise ValidationError(_("A schedule can never be prorated in both the entry and the exit month."))
        return lines

    def action_generate_lines(self):
        for rec in self:
            if rec.line_ids and rec.state != "draft":
                raise ValidationError(_("An active schedule is immutable; supersede it instead."))
            rec.line_ids.unlink()
            vals_list = rec._compute_schedule_lines(
                rec.date_of_birth, rec.monthly_amount, rec.age_limit_months, rec.cutoff_day
            )
            self.env["spp.entitlement.schedule.line"].create([dict(vals, schedule_id=rec.id) for vals in vals_list])
            rec.state = "active"

    @api.model
    def generate_for_membership(self, membership, manager):
        """Create (or return) the active schedule for a program membership.

        `manager` is the program's scheduled entitlement manager and carries
        the benefit configuration (amount, age limit, cut-off day).
        """
        program = membership.program_id
        partner = membership.partner_id
        existing = self.search(
            [("partner_id", "=", partner.id), ("program_id", "=", program.id), ("state", "=", "active")],
            limit=1,
        )
        if existing:
            return existing
        if not partner.birthdate:
            _logger.info("Schedule generation skipped: no date of birth (partner %s)", partner.id)
            return self.browse()
        schedule = self.create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "date_of_birth": partner.birthdate,
                "monthly_amount": manager.monthly_amount,
                "age_limit_months": manager.age_limit_months,
                "cutoff_day": manager.cutoff_day,
            }
        )
        schedule.action_generate_lines()
        return schedule


class EntitlementScheduleLine(models.Model):
    _name = "spp.entitlement.schedule.line"
    _description = "Entitlement Schedule Installment"
    _order = "benefit_month"

    schedule_id = fields.Many2one("spp.entitlement.schedule", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="schedule_id.partner_id", store=True, index=True)
    program_id = fields.Many2one(related="schedule_id.program_id", store=True, index=True)
    benefit_month = fields.Date(required=True, help="First day of the benefit month.")
    payable_from = fields.Date(required=True)
    payable_to = fields.Date(required=True)
    days_payable = fields.Integer(required=True)
    daily_rate = fields.Float(required=True)
    proration = fields.Selection(
        selection=[("none", "Full Month"), ("entry", "Entry (prorated)"), ("exit", "Exit (prorated)")],
        required=True,
        default="none",
    )
    amount = fields.Float(required=True)
    entitlement_id = fields.Many2one("spp.entitlement", string="Entitlement", readonly=True, index=True)
    # The disbursing cycle for this month, once its cycle has run. Empty for
    # months whose cycle has not been created yet.
    cycle_id = fields.Many2one("spp.cycle", related="entitlement_id.cycle_id", string="Cycle", store=False)
    payment_status = fields.Char(compute="_compute_payment_status")

    _unique_benefit_month = models.Constraint(
        "UNIQUE(schedule_id, benefit_month)",
        "Each benefit month can only appear once in a schedule.",
    )

    # A benefit month moves through this lifecycle as its payment cycle runs.
    # Kept as a small, citizen-friendly vocabulary rather than exposing the raw
    # entitlement/payment states.
    CANCELLED_ENTITLEMENT_STATES = ("rejected1", "rejected2", "rejected3", "cancelled", "expired")

    def _compute_payment_status(self):
        for rec in self:
            ent = rec.entitlement_id
            if not ent:
                # No entitlement yet: this month's payment cycle has not run.
                rec.payment_status = _("Scheduled")
                continue
            payments = ent.payment_ids
            if payments.filtered(lambda p: p.status == "paid"):
                rec.payment_status = _("Paid")
            elif payments and all(p.status == "failed" for p in payments):
                rec.payment_status = _("Failed")
            elif payments:
                # A payment has been generated in a batch and sent to the bank.
                rec.payment_status = _("In Payment")
            elif ent.state in self.CANCELLED_ENTITLEMENT_STATES:
                rec.payment_status = _("Cancelled")
            else:
                # Entitlement created for the month, but no payment/batch yet.
                rec.payment_status = _("Pending")
