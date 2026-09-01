# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Program creation wizard support for the Scheduled Cash entitlement.

Programs are created only through the program-creation wizard, so the
Scheduled Cash entitlement must be selectable there. This follows the same
extension pattern the platform uses elsewhere (see spp_program_geofence,
which adds a Geofence eligibility method to the same wizard): add the type to
the selection, add its inputs, and build the concrete manager plus its
wrapper in the corresponding `_get_*_manager` hook.

The Bank File (CSV) payment method is added the standard way — through the
Manager Setup dialog on the program — because it is registered on
`spp.program.payment.manager` via `_selection_manager_ref_id`.
"""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CreateProgramWizard(models.TransientModel):
    _inherit = "spp.program.create.wizard"

    entitlement_type = fields.Selection(
        selection_add=[("schedule", "Scheduled Cash (Child Benefit)")],
        ondelete={"schedule": "set default"},
    )
    schedule_monthly_amount = fields.Monetary(
        string="Monthly Benefit Amount",
        currency_field="currency_id",
        default=10000.0,
        help="Full benefit amount per calendar month.",
    )
    schedule_age_limit_months = fields.Integer(
        string="Benefit Age Limit (months)",
        default=36,
        help="Benefit ends in the month the child attains this age.",
    )
    schedule_cutoff_day = fields.Integer(
        string="Proration Cut-off Day",
        default=15,
        help="Born on or before this day: full entry month, prorated exit month. "
        "Born after it: prorated entry month, full exit month.",
    )

    @api.onchange("entitlement_type")
    def _onchange_entitlement_type_schedule_defaults(self):
        # Scheduled Cash benefits are amount-driven by the schedule, so
        # per-entitlement approval adds no value; default auto-approve on.
        if self.entitlement_type == "schedule":
            self.auto_approve_entitlements = True

    def _check_required_fields(self):
        # Follow the module's layering: run the standard checks (the parent's
        # cash/in-kind checks are guarded by entitlement_type, so they do not
        # fire for "schedule"), then add this type's own requirement.
        res = super()._check_required_fields()
        if self.entitlement_type == "schedule" and (
            not self.schedule_monthly_amount or self.schedule_monthly_amount <= 0
        ):
            raise ValidationError(_("The monthly benefit amount must be greater than zero."))
        return res

    def _get_entitlement_manager(self, program_id):
        if self.entitlement_type != "schedule":
            return super()._get_entitlement_manager(program_id)
        def_mgr = self.env["spp.program.entitlement.manager.schedule"].create(
            {
                "name": _("Scheduled Cash Entitlement"),
                "program_id": program_id,
                "monthly_amount": self.schedule_monthly_amount,
                "age_limit_months": self.schedule_age_limit_months,
                "cutoff_day": self.schedule_cutoff_day,
                "entitlement_validation_group_id": self.entitlement_validation_group_id.id,
                "approval_definition_id": self.entitlement_approval_definition_id.id or None,
            }
        )
        mgr = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": program_id,
                "manager_ref_id": f"spp.program.entitlement.manager.schedule,{def_mgr.id}",
            }
        )
        return {"entitlement_manager_ids": [Command.link(mgr.id)]}
