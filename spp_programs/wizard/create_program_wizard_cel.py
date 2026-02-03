# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL support for Create Program Wizard.

This module extends the program creation wizard to support CEL expressions
for eligibility, entitlement conditions, amount formulas, and compliance criteria.
"""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SPPCreateProgramWizardCEL(models.TransientModel):
    """Extend wizard with CEL eligibility and compliance support."""

    _inherit = "spp.program.create.wizard"

    # -------------------------------------------------------------------------
    # Eligibility Criteria Selection (Primary UX - template dropdown)
    # -------------------------------------------------------------------------
    eligibility_criteria_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Eligibility Criteria",
        domain="["
        "('expression_type', '=', 'filter'), "
        "('is_template', '=', True), "
        "('state', '=', 'active'), "
        "'|', "
        "('context_type', '=', target_type), "
        "('context_type', '=', 'both')"
        "]",
        help="Select who is eligible for this program. "
        "Leave empty for manual selection (no automatic filter). "
        "You can customize the expression in the Advanced section unless the template is locked.",
    )
    eligibility_is_locked = fields.Boolean(
        string="Criteria Locked",
        related="eligibility_criteria_id.is_locked",
        readonly=True,
        help="When checked, the eligibility expression cannot be modified.",
    )

    # -------------------------------------------------------------------------
    # CEL Profile (computed for widget context)
    # -------------------------------------------------------------------------
    eligibility_cel_profile = fields.Char(
        string="CEL Profile",
        compute="_compute_eligibility_cel_profile",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Eligibility CEL Fields
    # -------------------------------------------------------------------------
    eligibility_cel_expression = fields.Text(
        string="Eligibility CEL Expression",
        help="Define eligibility criteria using CEL syntax.\n"
        "Examples:\n"
        "- age_years(me.birthdate) >= 60\n"
        "- me.gender == 'female' and age_years(me.birthdate) >= 18\n"
        "- me.household_size >= 4",
    )
    eligibility_cel_preview_count = fields.Integer(
        string="Matching Beneficiaries",
        compute="_compute_eligibility_cel_preview",
        store=False,
    )
    eligibility_cel_is_valid = fields.Boolean(
        string="Expression Valid",
        compute="_compute_eligibility_cel_preview",
        store=False,
    )
    eligibility_cel_error = fields.Text(
        string="Expression Error",
        compute="_compute_eligibility_cel_preview",
        store=False,
    )
    eligibility_preview_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="wizard_eligibility_preview_partner_rel",
        column1="wizard_id",
        column2="partner_id",
        string="Preview Registrants",
        help="Partners matching the eligibility criteria (for preview)",
    )
    is_previewing = fields.Boolean(
        string="Is Previewing",
        default=False,
        help="Indicates if preview results are currently being displayed",
    )

    # -------------------------------------------------------------------------
    # Compliance Criteria (Optional)
    # -------------------------------------------------------------------------
    enable_compliance_cel = fields.Boolean(
        string="Enable Compliance Monitoring",
        default=False,
        help="Enable ongoing compliance criteria checking for beneficiaries.",
    )
    compliance_criteria_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Compliance Criteria",
        domain="["
        "('expression_type', '=', 'filter'), "
        "('is_template', '=', True), "
        "('state', '=', 'active'), "
        "'|', "
        "('context_type', '=', target_type), "
        "('context_type', '=', 'both')"
        "]",
        help="Select ongoing compliance criteria for beneficiaries. "
        "Beneficiaries must continue to meet these criteria.",
    )
    compliance_is_locked = fields.Boolean(
        string="Compliance Criteria Locked",
        related="compliance_criteria_id.is_locked",
        readonly=True,
        help="When checked, the compliance expression cannot be modified.",
    )
    compliance_cel_expression = fields.Text(
        string="Compliance CEL Expression",
        help="Define compliance criteria using CEL syntax.\n"
        "Beneficiaries must continue to meet these criteria.\n"
        "Example: me.last_health_checkup_date > today() - duration('90d')",
    )
    compliance_cel_preview_count = fields.Integer(
        string="Compliant Beneficiaries",
        compute="_compute_compliance_cel_preview",
        store=False,
    )
    compliance_cel_is_valid = fields.Boolean(
        string="Compliance Expression Valid",
        compute="_compute_compliance_cel_preview",
        store=False,
    )
    compliance_cel_error = fields.Text(
        string="Compliance Expression Error",
        compute="_compute_compliance_cel_preview",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    @api.depends("target_type")
    def _compute_eligibility_cel_profile(self):
        """Compute the CEL profile based on target type."""
        for rec in self:
            rec.eligibility_cel_profile = "registry_groups" if rec.target_type == "group" else "registry_individuals"

    @api.onchange("eligibility_criteria_id", "eligibility_cel_expression")
    def _onchange_eligibility_hide_preview(self):
        """Hide preview when eligibility criteria changes."""
        if self.is_previewing:
            self.is_previewing = False
            self.eligibility_preview_partner_ids = [(5, 0, 0)]

    @api.depends("eligibility_cel_expression", "target_type")
    def _compute_eligibility_cel_preview(self):
        """Compute preview count and validation for eligibility CEL expression."""
        for rec in self:
            rec.eligibility_cel_preview_count = 0
            rec.eligibility_cel_is_valid = True
            rec.eligibility_cel_error = ""

            if not rec.eligibility_cel_expression:
                continue

            try:
                profile = "registry_groups" if rec.target_type == "group" else "registry_individuals"
                service = self.env["spp.cel.service"]
                base_domain = [("disabled", "=", False)]

                result = service.compile_expression(
                    rec.eligibility_cel_expression,
                    profile=profile,
                    base_domain=base_domain,
                    limit=0,
                )

                if result.get("valid"):
                    rec.eligibility_cel_preview_count = result.get("count", 0)
                    rec.eligibility_cel_is_valid = True
                else:
                    rec.eligibility_cel_is_valid = False
                    rec.eligibility_cel_error = result.get("error", _("Unknown error"))
            except Exception as e:
                rec.eligibility_cel_is_valid = False
                rec.eligibility_cel_error = str(e)

    @api.depends("compliance_cel_expression", "target_type", "enable_compliance_cel")
    def _compute_compliance_cel_preview(self):
        """Compute preview count and validation for compliance CEL expression."""
        for rec in self:
            rec.compliance_cel_preview_count = 0
            rec.compliance_cel_is_valid = True
            rec.compliance_cel_error = ""

            if not rec.enable_compliance_cel or not rec.compliance_cel_expression:
                continue

            try:
                profile = "registry_groups" if rec.target_type == "group" else "registry_individuals"
                service = self.env["spp.cel.service"]
                base_domain = [("disabled", "=", False)]

                result = service.compile_expression(
                    rec.compliance_cel_expression,
                    profile=profile,
                    base_domain=base_domain,
                    limit=0,
                )

                if result.get("valid"):
                    rec.compliance_cel_preview_count = result.get("count", 0)
                    rec.compliance_cel_is_valid = True
                else:
                    rec.compliance_cel_is_valid = False
                    rec.compliance_cel_error = result.get("error", _("Unknown error"))
            except Exception as e:
                rec.compliance_cel_is_valid = False
                rec.compliance_cel_error = str(e)

    # -------------------------------------------------------------------------
    # Onchange Methods
    # -------------------------------------------------------------------------
    @api.onchange("target_type")
    def _onchange_target_type_clear_template(self):
        """Clear template selection when target type changes (templates are filtered)."""
        self.eligibility_criteria_id = False
        self.eligibility_cel_expression = False
        self.compliance_criteria_id = False
        self.compliance_cel_expression = False

    @api.onchange("eligibility_criteria_id")
    def _onchange_eligibility_criteria(self):
        """Populate expression when template is selected."""
        if self.eligibility_criteria_id:
            self.eligibility_cel_expression = self.eligibility_criteria_id.cel_expression

    @api.onchange("compliance_criteria_id")
    def _onchange_compliance_criteria(self):
        """Populate compliance expression when template is selected."""
        if self.compliance_criteria_id:
            self.compliance_cel_expression = self.compliance_criteria_id.cel_expression

    # -------------------------------------------------------------------------
    # Override Manager Creation Methods
    # -------------------------------------------------------------------------
    def _get_default_eligibility_manager_val(self, program_id):
        """Override to add CEL expression to eligibility manager.

        This adds both eligibility and compliance CEL expressions to the same
        eligibility manager, since compliance filtering is applied to already
        enrolled beneficiaries.
        """
        vals = super()._get_default_eligibility_manager_val(program_id)

        # Add CEL eligibility if expression provided
        if self.eligibility_cel_expression:
            vals.update(
                {
                    "eligibility_mode": "cel",
                    "cel_expression": self.eligibility_cel_expression,
                }
            )

        # Add template lineage tracking (Option C: Hybrid)
        if self.eligibility_criteria_id:
            vals.update(
                {
                    "source_expression_id": self.eligibility_criteria_id.id,
                    "is_eligibility_locked": self.eligibility_criteria_id.is_locked,
                }
            )

        # NOTE: Compliance is now handled by dedicated spp.compliance.manager.default
        # instead of being added to the eligibility manager.
        # See create_program() override below.

        return vals

    def create_program(self):
        """Override to create dedicated compliance manager when enabled."""
        action = super().create_program()

        # Create dedicated compliance manager if CEL compliance is enabled
        if self.enable_compliance_cel and self.compliance_cel_expression:
            program = self.env["spp.program"].browse(action["res_id"])
            self._create_cel_compliance_manager(program)

        return action

    def _create_cel_compliance_manager(self, program):
        """Create a dedicated compliance manager with CEL expression."""
        self.ensure_one()
        program.ensure_one()

        # Build values for compliance manager
        vals = {
            "name": f"{program.name} Compliance",
            "program_id": program.id,
            "compliance_cel_expression": self.compliance_cel_expression,
        }

        # Add template lineage tracking if criteria template is selected
        if self.compliance_criteria_id:
            vals.update({
                "source_expression_id": self.compliance_criteria_id.id,
                "is_compliance_locked": self.compliance_criteria_id.is_locked,
            })

        # Create the compliance manager implementation
        compliance_impl = self.env["spp.compliance.manager.default"].sudo().create(vals)

        # Create the wrapper and link to program
        program.write({
            "compliance_manager_ids": [
                Command.create({
                    "manager_ref_id": f"spp.compliance.manager.default,{compliance_impl.id}",
                }),
            ],
        })

    def _check_required_fields(self):
        """Override to validate CEL expressions before program creation."""
        res = super()._check_required_fields()

        # Validate eligibility CEL if provided
        if self.eligibility_cel_expression and not self.eligibility_cel_is_valid:
            raise UserError(_("Eligibility CEL expression is invalid: %s") % self.eligibility_cel_error)

        # Validate compliance CEL if enabled
        if self.enable_compliance_cel:
            if not self.compliance_cel_expression:
                raise UserError(_("Compliance CEL expression is required when compliance monitoring is enabled."))
            if not self.compliance_cel_is_valid:
                raise UserError(_("Compliance CEL expression is invalid: %s") % self.compliance_cel_error)

        # Validate cash item CEL expressions
        if self.entitlement_type == "cash":
            for idx, item in enumerate(self.entitlement_cash_item_ids, 1):
                if hasattr(item, "cel_is_valid") and not item.cel_is_valid:
                    raise UserError(
                        _("Cash item %d has invalid CEL expression: %s") % (idx, item.cel_error or _("Unknown error"))
                    )

        # Validate in-kind item CEL expressions
        if self.entitlement_type == "inkind":
            for idx, item in enumerate(self.entitlement_item_ids, 1):
                if hasattr(item, "quantity_cel_is_valid") and not item.quantity_cel_is_valid:
                    raise UserError(
                        _("In-kind item %d has invalid quantity formula: %s")
                        % (idx, item.quantity_cel_error or _("Unknown error"))
                    )
                if hasattr(item, "condition_cel_is_valid") and item.has_condition and not item.condition_cel_is_valid:
                    raise UserError(
                        _("In-kind item %d has invalid condition expression: %s")
                        % (idx, item.condition_cel_error or _("Unknown error"))
                    )

        return res

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------
    def action_preview_eligibility(self):
        """Preview beneficiaries matching eligibility CEL expression."""
        self.ensure_one()
        if not self.eligibility_cel_expression:
            raise UserError(_("Please enter a CEL expression first."))

        if not self.eligibility_cel_is_valid:
            raise UserError(_("Cannot preview invalid expression: %s") % self.eligibility_cel_error)

        try:
            profile = "registry_groups" if self.target_type == "group" else "registry_individuals"
            service = self.env["spp.cel.service"]
            result = service.compile_expression(
                self.eligibility_cel_expression,
                profile=profile,
                base_domain=[("disabled", "=", False)],
                limit=100,  # Limit to 100 for preview
                materialize_sql=True,  # Required for window actions - domain must be serializable
            )

            # Update wizard with preview results
            self.write(
                {
                    "eligibility_preview_partner_ids": [(6, 0, result.get("ids", []))],
                    "is_previewing": True,
                }
            )

            # Reload the form to show the preview tab
            return {
                "type": "ir.actions.act_window",
                "name": _("Set Program Settings"),
                "res_model": "spp.program.create.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
                "context": self.env.context,
            }
        except Exception as e:
            raise UserError(_("Error previewing expression: %s") % str(e)) from e

    def action_hide_preview(self):
        """Hide the preview results."""
        self.ensure_one()
        self.write(
            {
                "eligibility_preview_partner_ids": [(5, 0, 0)],  # Clear all
                "is_previewing": False,
            }
        )

        # Reload the form
        return {
            "type": "ir.actions.act_window",
            "name": _("Set Program Settings"),
            "res_model": "spp.program.create.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def _get_entitlement_manager(self, program_id):
        """Override to add CEL fields to entitlement items."""
        # For cash entitlement, prepare items with CEL fields
        if self.entitlement_type == "cash":
            entitlement_item_ids = []
            for item in self.entitlement_cash_item_ids:
                item_vals = {
                    "sequence": item.sequence,
                    "currency_id": item.currency_id.id,
                    "multiplier_field": item.multiplier_field.id if item.multiplier_field else False,
                    "max_multiplier": item.max_multiplier,
                }

                # Amount: CEL or Fixed
                if hasattr(item, "amount_mode") and item.amount_mode == "cel":
                    item_vals.update(
                        {
                            "amount_mode": "cel",
                            "amount_cel_expression": item.amount_cel_expression or "",
                            "amount": item.amount,  # base_amount for formula
                        }
                    )
                else:
                    item_vals["amount"] = item.amount

                # Condition: CEL or Domain
                if hasattr(item, "has_condition") and item.has_condition:
                    if hasattr(item, "condition_mode") and item.condition_mode == "cel":
                        item_vals.update(
                            {
                                "condition_mode": "cel",
                                "cel_condition": item.cel_condition or "",
                            }
                        )
                    else:
                        item_vals["condition"] = item.condition or ""
                else:
                    item_vals["condition"] = item.condition or ""

                entitlement_item_ids.append(Command.create(item_vals))

            def_mgr_obj = "spp.program.entitlement.manager.cash"
            def_mgr = self.env[def_mgr_obj].create(
                {
                    "name": "Cash",
                    "program_id": program_id,
                    "is_evaluate_one_item": self.is_evaluate_one_item,
                    "entitlement_item_ids": entitlement_item_ids,
                    "max_amount": self.max_amount,
                    "entitlement_validation_group_id": self.entitlement_validation_group_id.id,
                    "id_type_id": self.id_type_id.id if self.id_type_id else False,
                    "approval_definition_id": self.entitlement_approval_definition_id.id
                    if self.entitlement_approval_definition_id
                    else False,
                }
            )

            man_obj = self.env["spp.program.entitlement.manager"]
            mgr = man_obj.create(
                {
                    "program_id": program_id,
                    "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
                }
            )
            return {"entitlement_manager_ids": [(4, mgr.id)]}

        # For in-kind entitlement, prepare items with CEL fields
        elif self.entitlement_type == "inkind":
            entitlement_item_ids = []
            for item in self.entitlement_item_ids:
                item_vals = {
                    "sequence": item.sequence,
                    "product_id": item.product_id.id,
                    "multiplier_field": item.multiplier_field.id if item.multiplier_field else False,
                    "max_multiplier": item.max_multiplier,
                }

                # Quantity: CEL or Fixed
                if hasattr(item, "quantity_mode") and item.quantity_mode == "cel":
                    item_vals.update(
                        {
                            "quantity_mode": "cel",
                            "quantity_cel_expression": item.quantity_cel_expression or "",
                            "quantity": item.quantity,  # base_quantity for formula
                        }
                    )
                else:
                    item_vals["quantity"] = item.quantity

                # Condition: CEL or Domain
                if hasattr(item, "has_condition") and item.has_condition:
                    if hasattr(item, "condition_mode") and item.condition_mode == "cel":
                        item_vals.update(
                            {
                                "condition_mode": "cel",
                                "condition_cel_expression": item.condition_cel_expression or "",
                            }
                        )
                    else:
                        item_vals["condition"] = item.condition or ""
                else:
                    item_vals["condition"] = item.condition or ""

                entitlement_item_ids.append(Command.create(item_vals))

            def_mgr_obj = "spp.program.entitlement.manager.inkind"
            def_mgr = self.env[def_mgr_obj].create(
                {
                    "name": "In-kind",
                    "program_id": program_id,
                    "is_evaluate_single_item": self.is_evaluate_single_item,
                    "entitlement_item_ids": entitlement_item_ids,
                    "entitlement_validation_group_id": self.entitlement_validation_group_id.id,
                    "id_type_id": self.id_type_id.id if self.id_type_id else False,
                    "manage_inventory": self.manage_inventory,
                    "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
                    "approval_definition_id": self.entitlement_approval_definition_id.id
                    if self.entitlement_approval_definition_id
                    else False,
                }
            )

            man_obj = self.env["spp.program.entitlement.manager"]
            mgr = man_obj.create(
                {
                    "program_id": program_id,
                    "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
                }
            )
            return {"entitlement_manager_ids": [(4, mgr.id)]}

        # Default: use parent implementation
        return super()._get_entitlement_manager(program_id)


class SPPCreateProgramWizardCashItemCEL(models.TransientModel):
    """Extend cash entitlement item with CEL support."""

    _inherit = "spp.program.create.wizard.entitlement.cash.item"

    # -------------------------------------------------------------------------
    # Condition Template Selection (Primary UX)
    # -------------------------------------------------------------------------
    condition_template_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Condition",
        domain="[" "('expression_type', '=', 'filter'), " "('is_template', '=', True), " "('state', '=', 'active')" "]",
        help="Select a condition to restrict which beneficiaries receive this item. "
        "Leave empty to apply to all eligible beneficiaries.",
    )
    condition_is_locked = fields.Boolean(
        string="Condition Locked",
        related="condition_template_id.is_locked",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Amount Formula Template Selection
    # -------------------------------------------------------------------------
    amount_template_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Amount Formula",
        domain="["
        "('expression_type', '=', 'formula'), "
        "('output_type', '=', 'money'), "
        "('is_template', '=', True), "
        "('state', '=', 'active')"
        "]",
        help="Select a formula to calculate the amount. " "Leave empty for a fixed amount.",
    )
    amount_is_locked = fields.Boolean(
        string="Amount Formula Locked",
        related="amount_template_id.is_locked",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Amount CEL Fields
    # -------------------------------------------------------------------------
    amount_mode = fields.Selection(
        selection=[
            ("fixed", "Fixed Amount"),
            ("cel", "CEL Formula"),
        ],
        string="Amount Mode",
        default="fixed",
        help="Choose between fixed amount or dynamic CEL formula.",
    )
    amount_cel_expression = fields.Text(
        string="Amount Formula",
        help="Formula to calculate amount using CEL syntax.\n"
        "Available: me (beneficiary), base_amount\n"
        "Examples:\n"
        "- 500 (fixed)\n"
        "- me.household_size * 100\n"
        "- base_amount * (1 + me.dependents_count * 0.1)",
    )
    amount_cel_preview = fields.Char(
        string="Amount Preview",
        compute="_compute_amount_cel_preview",
        store=False,
    )
    amount_cel_is_valid = fields.Boolean(
        string="Amount Formula Valid",
        compute="_compute_amount_cel_preview",
        store=False,
    )
    amount_cel_error = fields.Text(
        string="Amount Formula Error",
        compute="_compute_amount_cel_preview",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Condition CEL Fields
    # -------------------------------------------------------------------------
    has_condition = fields.Boolean(
        string="Apply Condition",
        default=False,
        help="Enable to restrict this item to specific beneficiaries.",
    )
    condition_mode = fields.Selection(
        selection=[
            ("domain", "Domain Filter"),
            ("cel", "CEL Expression"),
        ],
        string="Condition Mode",
        default="cel",
        help="Choose how to define the condition.",
    )
    cel_condition = fields.Text(
        string="CEL Condition",
        help="Condition expression using CEL syntax.\n"
        "Examples:\n"
        "- me.has_disability == true\n"
        "- me.household_size >= 4\n"
        "- age_years(me.birthdate) >= 60",
    )
    cel_preview_count = fields.Integer(
        string="Matching Count",
        compute="_compute_condition_cel_preview",
        store=False,
    )
    cel_is_valid = fields.Boolean(
        string="Condition Valid",
        compute="_compute_condition_cel_preview",
        store=False,
    )
    cel_error = fields.Text(
        string="Condition Error",
        compute="_compute_condition_cel_preview",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    @api.depends("amount_mode", "amount_cel_expression", "amount")
    def _compute_amount_cel_preview(self):
        """Compute preview and validation for amount CEL formula."""
        for rec in self:
            rec.amount_cel_preview = ""
            rec.amount_cel_is_valid = True
            rec.amount_cel_error = ""

            if rec.amount_mode != "cel" or not rec.amount_cel_expression:
                continue

            try:
                # Validate by attempting to compile the expression
                # Use Python's compile as a basic syntax check
                compile(rec.amount_cel_expression, "<string>", "eval")
                rec.amount_cel_is_valid = True
                rec.amount_cel_preview = _("Formula syntax is valid")
            except SyntaxError as e:
                rec.amount_cel_is_valid = False
                rec.amount_cel_error = _("Syntax error: %s") % str(e)

    @api.depends("has_condition", "condition_mode", "cel_condition", "program_id.target_type")
    def _compute_condition_cel_preview(self):
        """Compute preview and validation for condition CEL expression."""
        for rec in self:
            rec.cel_preview_count = 0
            rec.cel_is_valid = True
            rec.cel_error = ""

            if not rec.has_condition:
                continue

            if rec.condition_mode != "cel" or not rec.cel_condition:
                rec.cel_is_valid = rec.condition_mode == "domain"
                continue

            try:
                target_type = rec.program_id.target_type if rec.program_id else "individual"
                profile = "registry_groups" if target_type == "group" else "registry_individuals"
                service = self.env["spp.cel.service"]
                result = service.compile_expression(
                    rec.cel_condition,
                    profile=profile,
                    base_domain=[("disabled", "=", False)],
                    limit=0,
                )

                if result.get("valid"):
                    rec.cel_preview_count = result.get("count", 0)
                    rec.cel_is_valid = True
                else:
                    rec.cel_is_valid = False
                    rec.cel_error = result.get("error", _("Unknown error"))
            except Exception as e:
                rec.cel_is_valid = False
                rec.cel_error = str(e)

    # -------------------------------------------------------------------------
    # Onchange Methods for Template Selection
    # -------------------------------------------------------------------------
    @api.onchange("condition_template_id")
    def _onchange_condition_template(self):
        """Populate condition expression when template is selected."""
        if self.condition_template_id:
            self.has_condition = True
            self.condition_mode = "cel"
            self.cel_condition = self.condition_template_id.cel_expression

    @api.onchange("amount_template_id")
    def _onchange_amount_template(self):
        """Populate amount formula when template is selected."""
        if self.amount_template_id:
            self.amount_mode = "cel"
            self.amount_cel_expression = self.amount_template_id.cel_expression


class SPPCreateProgramWizardInKindItemCEL(models.TransientModel):
    """Extend in-kind entitlement item with CEL support."""

    _inherit = "spp.program.create.wizard.entitlement.item"

    # -------------------------------------------------------------------------
    # Condition Template Selection (Primary UX)
    # -------------------------------------------------------------------------
    condition_template_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Condition",
        domain="[" "('expression_type', '=', 'filter'), " "('is_template', '=', True), " "('state', '=', 'active')" "]",
        help="Select a condition to restrict which beneficiaries receive this item. "
        "Leave empty to apply to all eligible beneficiaries.",
    )
    condition_is_locked = fields.Boolean(
        string="Condition Locked",
        related="condition_template_id.is_locked",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Quantity Formula Template Selection
    # -------------------------------------------------------------------------
    quantity_template_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Quantity Formula",
        domain="["
        "('expression_type', '=', 'formula'), "
        "('output_type', '=', 'number'), "
        "('is_template', '=', True), "
        "('state', '=', 'active')"
        "]",
        help="Select a formula to calculate the quantity. " "Leave empty for a fixed quantity.",
    )
    quantity_is_locked = fields.Boolean(
        string="Quantity Formula Locked",
        related="quantity_template_id.is_locked",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Quantity CEL Fields
    # -------------------------------------------------------------------------
    quantity_mode = fields.Selection(
        selection=[
            ("fixed", "Fixed Quantity"),
            ("cel", "CEL Formula"),
        ],
        string="Quantity Mode",
        default="fixed",
        help="Choose between fixed quantity or dynamic CEL formula.",
    )
    quantity_cel_expression = fields.Text(
        string="Quantity Formula",
        help="Formula to calculate quantity using CEL syntax.\n"
        "Examples:\n"
        "- me.household_size * 2\n"
        "- base_quantity + me.children_count\n"
        "- 10 if me.is_woman_headed else 8",
    )
    quantity_cel_preview = fields.Char(
        string="Quantity Preview",
        compute="_compute_quantity_cel_preview",
        store=False,
    )
    quantity_cel_is_valid = fields.Boolean(
        string="Quantity Formula Valid",
        compute="_compute_quantity_cel_preview",
        store=False,
    )
    quantity_cel_error = fields.Text(
        string="Quantity Formula Error",
        compute="_compute_quantity_cel_preview",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Condition CEL Fields
    # -------------------------------------------------------------------------
    has_condition = fields.Boolean(
        string="Apply Condition",
        default=False,
        help="Enable to restrict this item to specific beneficiaries.",
    )
    condition_mode = fields.Selection(
        selection=[
            ("domain", "Domain Filter"),
            ("cel", "CEL Expression"),
        ],
        string="Condition Mode",
        default="cel",
        help="Choose how to define the condition.",
    )
    condition_cel_expression = fields.Text(
        string="Condition CEL Expression",
        help="Condition expression using CEL syntax.\n"
        "Examples:\n"
        "- me.household_size >= 4\n"
        "- me.has_young_children == true",
    )
    condition_cel_preview_count = fields.Integer(
        string="Matching Count",
        compute="_compute_condition_cel_preview",
        store=False,
    )
    condition_cel_is_valid = fields.Boolean(
        string="Condition Valid",
        compute="_compute_condition_cel_preview",
        store=False,
    )
    condition_cel_error = fields.Text(
        string="Condition Error",
        compute="_compute_condition_cel_preview",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    @api.depends("quantity_mode", "quantity_cel_expression", "quantity")
    def _compute_quantity_cel_preview(self):
        """Compute preview and validation for quantity CEL formula."""
        for rec in self:
            rec.quantity_cel_preview = ""
            rec.quantity_cel_is_valid = True
            rec.quantity_cel_error = ""

            if rec.quantity_mode != "cel" or not rec.quantity_cel_expression:
                continue

            try:
                # Validate by attempting to compile the expression
                compile(rec.quantity_cel_expression, "<string>", "eval")
                rec.quantity_cel_is_valid = True
                rec.quantity_cel_preview = _("Formula syntax is valid")
            except SyntaxError as e:
                rec.quantity_cel_is_valid = False
                rec.quantity_cel_error = _("Syntax error: %s") % str(e)

    @api.depends("has_condition", "condition_mode", "condition_cel_expression", "program_id.target_type")
    def _compute_condition_cel_preview(self):
        """Compute preview and validation for condition CEL expression."""
        for rec in self:
            rec.condition_cel_preview_count = 0
            rec.condition_cel_is_valid = True
            rec.condition_cel_error = ""

            if not rec.has_condition:
                continue

            if rec.condition_mode != "cel" or not rec.condition_cel_expression:
                rec.condition_cel_is_valid = rec.condition_mode == "domain"
                continue

            try:
                target_type = rec.program_id.target_type if rec.program_id else "group"
                profile = "registry_groups" if target_type == "group" else "registry_individuals"
                service = self.env["spp.cel.service"]
                result = service.compile_expression(
                    rec.condition_cel_expression,
                    profile=profile,
                    base_domain=[("disabled", "=", False)],
                    limit=0,
                )

                if result.get("valid"):
                    rec.condition_cel_preview_count = result.get("count", 0)
                    rec.condition_cel_is_valid = True
                else:
                    rec.condition_cel_is_valid = False
                    rec.condition_cel_error = result.get("error", _("Unknown error"))
            except Exception as e:
                rec.condition_cel_is_valid = False
                rec.condition_cel_error = str(e)

    # -------------------------------------------------------------------------
    # Onchange Methods for Template Selection
    # -------------------------------------------------------------------------
    @api.onchange("condition_template_id")
    def _onchange_condition_template(self):
        """Populate condition expression when template is selected."""
        if self.condition_template_id:
            self.has_condition = True
            self.condition_mode = "cel"
            self.condition_cel_expression = self.condition_template_id.cel_expression

    @api.onchange("quantity_template_id")
    def _onchange_quantity_template(self):
        """Populate quantity formula when template is selected."""
        if self.quantity_template_id:
            self.quantity_mode = "cel"
            self.quantity_cel_expression = self.quantity_template_id.cel_expression
