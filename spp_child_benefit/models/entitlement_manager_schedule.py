# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spp_programs.models import constants

_logger = logging.getLogger(__name__)


class EntitlementManager(models.Model):
    _inherit = "spp.program.entitlement.manager"

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = ("spp.program.entitlement.manager.schedule", "Scheduled Cash")
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class ScheduleEntitlementManager(models.Model):
    """Cash entitlements driven by a pre-generated benefit schedule.

    Amounts are never computed at cycle time: enrollment generates the full
    benefit schedule, and each cycle materializes the schedule installments
    that fall inside the cycle period into standard entitlements. Approval,
    validation, and payment flows are inherited from the cash manager.
    """

    _name = "spp.program.entitlement.manager.schedule"
    _inherit = "spp.program.entitlement.manager.cash"
    _description = "Scheduled Cash Entitlement Manager"

    monthly_amount = fields.Float(
        default=10000.0,
        required=True,
        help="Full benefit amount per calendar month.",
    )
    age_limit_months = fields.Integer(
        default=36,
        required=True,
        help="Benefit ends in the month the beneficiary attains this age.",
    )
    cutoff_day = fields.Integer(
        default=15,
        required=True,
        help="Day-of-month proration cut-off (see the benefit schedule).",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "name" in fields_list:
            res["name"] = _("Scheduled Cash Entitlement")
        return res

    def ensure_schedule(self, membership):
        return self.env["spp.entitlement.schedule"].generate_for_membership(membership, self)

    def prepare_entitlements(self, cycle, beneficiaries):
        """Materialize schedule installments for the cycle period.

        :param cycle: the cycle being prepared
        :param beneficiaries: cycle membership records (enrolled)
        """
        self.ensure_one()
        Line = self.env["spp.entitlement.schedule.line"]
        partners = beneficiaries.mapped("partner_id")
        program_memberships = self.env["spp.program.membership"].search(
            [("program_id", "=", self.program_id.id), ("partner_id", "in", partners.ids)]
        )
        for membership in program_memberships:
            self.ensure_schedule(membership)

        lines = Line.search(
            [
                ("program_id", "=", self.program_id.id),
                ("partner_id", "in", partners.ids),
                ("schedule_id.state", "=", "active"),
                ("entitlement_id", "=", False),
                ("benefit_month", ">=", cycle.start_date),
                ("benefit_month", "<=", cycle.end_date),
            ]
        )
        if not lines:
            _logger.info("No schedule installments to materialize for cycle %s", cycle.id)
            return

        journal = self.program_id.journal_id
        if not journal:
            raise UserError(
                _("Programme %s has no journal; a journal is required to prepare payments.") % self.program_id.name
            )
        currency_id = (journal.currency_id or self.env.company.currency_id).id
        vals_list = []
        for line in lines:
            vals_list.append(
                {
                    "cycle_id": cycle.id,
                    "partner_id": line.partner_id.id,
                    "initial_amount": line.amount,
                    "currency_id": currency_id,
                    "state": "draft",
                    "is_cash_entitlement": True,
                    "valid_from": line.payable_from,
                    "valid_until": line.payable_to,
                }
            )
        entitlements = self.env["spp.entitlement"].create(vals_list)
        for line, entitlement in zip(lines, entitlements, strict=False):
            line.entitlement_id = entitlement


class ProgramMembershipSchedule(models.Model):
    _inherit = "spp.program.membership"

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "enrolled":
            self._generate_benefit_schedules()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(lambda r: r.state == "enrolled")._generate_benefit_schedules()
        return records

    def _generate_benefit_schedules(self):
        for rec in self:
            manager = rec.program_id.get_manager(constants.MANAGER_ENTITLEMENT)
            if manager and manager._name == "spp.program.entitlement.manager.schedule":
                manager.ensure_schedule(rec)
