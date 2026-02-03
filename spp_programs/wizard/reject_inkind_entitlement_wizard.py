# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RejectInKindEntitlementWiz(models.TransientModel):
    _name = "spp.reject.inkind.entitlement.wizard"
    _description = "Reject In-Kind Entitlement Wizard"

    def entitlement_state_to_add(self):
        return ["draft", "pending_validation"]

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get("active_ids"):
            entitlement_ids = []

            for rec in self.env.context.get("active_ids"):
                entitlement = self.env["spp.entitlement.inkind"].search(
                    [
                        ("id", "=", rec),
                    ]
                )
                if entitlement.state in self.entitlement_state_to_add():
                    entitlement_ids.append([0, 0, {"entitlement_id": rec}])

            res["entitlement_ids"] = entitlement_ids
        if self.env.context.get("to_state"):
            res["to_state"] = self.env.context.get("to_state")

        return res

    entitlement_ids = fields.One2many(
        "spp.inkind.entitlement.reject",
        "wizard_id",
        string="Entitlements",
        required=True,
    )
    number_of_beneficiaries = fields.Integer(
        compute="_compute_number_of_beneficiaries",
        string="Number of Beneficiaries",
    )
    reject_reason = fields.Text(string="Reason")
    to_state = fields.Char("To State", default="reject")

    @api.depends("entitlement_ids")
    def _compute_number_of_beneficiaries(self):
        self.number_of_beneficiaries = len(self.entitlement_ids)

    def reject_entitlements(self):
        if self.entitlement_ids:
            return self.entitlement_ids.entitlement_id._reject_entitlement(
                to_state=self.to_state, reject_reason=self.reject_reason
            )

    def open_wizard(self):
        _logger.info("In-Kind Entitlement IDs: %s", self.env.context.get("active_ids"))
        return {
            "name": "Reject In-Kind Entitlement",
            "view_mode": "form",
            "res_model": "spp.reject.inkind.entitlement.wizard",
            "view_id": self.env.ref("spp_programs.reject_inkind_entitlement_wizard").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "nodestroy": True,
            "context": self.env.context,
        }

    def close_wizard(self):
        return {"type": "ir.actions.act_window_close"}


class SPPInKindEntitlementReject(models.TransientModel):
    _name = "spp.inkind.entitlement.reject"
    _description = "Multi In-Kind Entitlement Reject"

    entitlement_id = fields.Many2one(
        "spp.entitlement.inkind",
        "In-Kind Entitlement",
        help="An In-Kind Entitlement",
        required=True,
    )
    cycle_id = fields.Many2one(
        "spp.cycle",
        "Cycle",
        help="A Cycle",
        related="entitlement_id.cycle_id",
    )
    wizard_id = fields.Many2one(
        "spp.reject.inkind.entitlement.wizard",
        "Reject In-Kind Entitlement Wizard",
        help="A Wizard",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        help="A beneficiary",
        related="entitlement_id.partner_id",
    )
    code = fields.Char(related="entitlement_id.code")
    product_id = fields.Many2one("product.product", "Product", related="entitlement_id.product_id")
    quantity = fields.Integer("Quantity", related="entitlement_id.quantity")
    currency_id = fields.Many2one("res.currency", related="entitlement_id.currency_id")
    total_amount = fields.Monetary(
        string="Total Value",
        currency_field="currency_id",
        related="entitlement_id.total_amount",
        readonly=True,
    )
