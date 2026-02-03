from odoo import _, api, fields, models


class MultiEntitlementApprovalWiz(models.TransientModel):
    _name = "spp.multi.entitlement.approval.wizard"
    _description = "Multi Entitlement Approval Wizard"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get("active_ids"):
            entitlement_ids = []
            for rec in self.env.context.get("active_ids"):
                entitlement = self.env["spp.entitlement"].search([("id", "=", rec)])
                if entitlement.state in ("draft", "pending_validation"):
                    entitlement_ids.append([0, 0, {"entitlement_id": rec}])
            res["entitlement_ids"] = entitlement_ids
        return res

    entitlement_ids = fields.One2many(
        "spp.multi.entitlement.approval",
        "wizard_id",
        string="Entitlements",
        required=True,
    )

    number_of_beneficiaries = fields.Integer(
        compute="_compute_number_of_beneficiaries",
        string="Number of Beneficiaries",
    )

    # Fund availability fields
    has_sufficient_funds = fields.Boolean(
        compute="_compute_fund_availability",
        string="Has Sufficient Funds",
    )
    fund_availability_message = fields.Text(
        compute="_compute_fund_availability",
        string="Fund Availability Message",
    )
    available_funds = fields.Monetary(
        compute="_compute_fund_availability",
        currency_field="currency_id",
        string="Available Funds",
    )
    required_funds = fields.Monetary(
        compute="_compute_fund_availability",
        currency_field="currency_id",
        string="Required Funds",
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_fund_availability",
        string="Currency",
    )

    @api.depends("entitlement_ids")
    def _compute_number_of_beneficiaries(self):
        self.number_of_beneficiaries = len(self.entitlement_ids)

    @api.depends("entitlement_ids", "entitlement_ids.entitlement_id.initial_amount")
    def _compute_fund_availability(self):
        """Compute fund availability for entitlements to be approved."""
        for rec in self:
            # Default values
            rec.has_sufficient_funds = True
            rec.fund_availability_message = ""
            rec.available_funds = 0.0
            rec.required_funds = 0.0
            rec.currency_id = False

            if not rec.entitlement_ids:
                continue

            entitlements = rec.entitlement_ids.mapped("entitlement_id")
            if not entitlements:
                continue

            # Get program from first entitlement (all should be from same program)
            first_entitlement = entitlements[0]
            program = first_entitlement.cycle_id.program_id
            if not program:
                continue

            # Set currency
            rec.currency_id = first_entitlement.currency_id

            # Get entitlement manager
            from ..models import constants

            entitlement_manager = program.get_manager(constants.MANAGER_ENTITLEMENT)
            if not entitlement_manager or not entitlement_manager.IS_CASH_ENTITLEMENT:
                continue

            # Calculate required funds
            required_funds = sum(entitlements.mapped("initial_amount"))
            rec.required_funds = required_funds

            # Get available funds
            available_funds = entitlement_manager.check_fund_balance(program.id)
            rec.available_funds = available_funds

            # Check if sufficient
            if available_funds < required_funds:
                rec.has_sufficient_funds = False
                shortage = required_funds - available_funds
                rec.fund_availability_message = _(
                    "Insufficient funds to approve all selected entitlements!\n"
                    "Available: %(available).2f | Required: %(required).2f | Shortage: %(shortage).2f\n\n"
                    "Tip: You can remove some entitlements from the list below to reduce the required amount, "
                    "or add funds to the program before approving."
                ) % {
                    "available": available_funds,
                    "required": required_funds,
                    "shortage": shortage,
                }
            else:
                rec.has_sufficient_funds = True
                surplus = available_funds - required_funds
                rec.fund_availability_message = _(
                    "Sufficient funds available to approve all selected entitlements.\n"
                    "Available: %(available).2f | Required: %(required).2f | Remaining: %(surplus).2f"
                ) % {
                    "available": available_funds,
                    "required": required_funds,
                    "surplus": surplus,
                }

    def approve_entitlements(self):
        if self.entitlement_ids:
            entitlements = self.entitlement_ids.mapped("entitlement_id")
            result = entitlements.action_approve()
            # If approve_entitlement returned an error, return it
            if result:
                return result
            # Otherwise show success notification and close the wizard
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Entitlements Approved"),
                    "message": _("%d entitlement(s) have been successfully approved.") % len(entitlements),
                    "sticky": False,
                    "type": "success",
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def open_wizard(self):
        return {
            "name": "Multiple Entitlements Approval",
            "view_mode": "form",
            "res_model": "spp.multi.entitlement.approval.wizard",
            "view_id": self.env.ref("spp_programs.multi_entitlement_approval_wizard_form_view").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "nodestroy": True,
            "context": self.env.context,
        }

    def close_wizard(self):
        return {"type": "ir.actions.act_window_close"}


class MultiEntitlementApproval(models.TransientModel):
    _name = "spp.multi.entitlement.approval"
    _description = "Multi Entitlement Approval"

    entitlement_id = fields.Many2one(
        "spp.entitlement",
        "Entitlement",
        required=True,
    )
    wizard_id = fields.Many2one(
        "spp.multi.entitlement.approval.wizard",
        "Multi Entitlement Approval Wizard",
        required=True,
    )
    cycle_id = fields.Many2one(
        "spp.cycle",
        "Cycle",
        related="entitlement_id.cycle_id",
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        related="entitlement_id.partner_id",
    )
    code = fields.Char(related="entitlement_id.code")
    initial_amount = fields.Monetary(
        string="Initial Amount",
        currency_field="currency_id",
        related="entitlement_id.initial_amount",
    )
    currency_id = fields.Many2one("res.currency", related="entitlement_id.currency_id")
