# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv.expression import AND, OR

# from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPCreateProgramWizardBase(models.TransientModel):
    _name = "spp.program.create.wizard"
    _description = "Create Program Wizard"

    name = fields.Char("Program Name", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        "Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    target_type = fields.Selection(
        [("individual", "Individual"), ("group", "Group")],
        "Target Type",
        default="individual",
        required=True,
    )
    state = fields.Selection(
        [("step1", "Program"), ("step2", "Rules")],
        default="step1",
    )
    eligibility_domain = fields.Char("Eligibility Domain", default="[]")
    auto_approve_entitlements = fields.Boolean("Auto Approve Entitlements", default=False)
    cycle_duration = fields.Integer("Cycle Duration", default=1)
    approver_group_id = fields.Many2one("res.groups", "Approver Group")
    entitlement_type = fields.Selection(
        [("cash", "Cash"), ("inkind", "In-Kind")],
        "Benefit Type",
        default="cash",
    )
    amount_per_cycle = fields.Monetary("Amount per Cycle", currency_field="currency_id")
    amount_per_individual_in_group = fields.Monetary("Amount per Individual in Group", currency_field="currency_id")
    transfer_fee_pct = fields.Float("Transfer Fee (%)", default=0.0)
    transfer_fee_amt = fields.Monetary("Transfer Fee Amount", currency_field="currency_id", default=0.0)
    max_individual_in_group = fields.Integer("Max Individual in Group", default=0)
    entitlement_validation_group_id = fields.Many2one("res.groups", "Entitlement Validation Group")

    # Cash Entitlement Manager fields
    is_evaluate_one_item = fields.Boolean(default=False)
    entitlement_cash_item_ids = fields.One2many(
        "spp.program.create.wizard.entitlement.cash.item",
        "program_id",
        "Cash Entitlement Items",
    )
    max_amount = fields.Monetary(
        string="Maximum Amount",
        currency_field="currency_id",
        default=0.0,
    )

    import_beneficiaries = fields.Selection(
        [("no", "No"), ("yes", "Yes")],
        "Import Beneficiaries",
        default="no",
    )
    rrule_type = fields.Selection(
        [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        "Recurrence",
        default="monthly",
    )
    # Recurrence fields for weekly
    mon = fields.Boolean("Monday")
    tue = fields.Boolean("Tuesday")
    wed = fields.Boolean("Wednesday")
    thu = fields.Boolean("Thursday")
    fri = fields.Boolean("Friday")
    sat = fields.Boolean("Saturday")
    sun = fields.Boolean("Sunday")

    # Recurrence fields for monthly
    month_by = fields.Selection(
        [
            ("date", "Date of month"),
            ("day", "Day of month"),
        ],
        "Month By",
        default="date",
    )
    day = fields.Integer("Day of Month", default=1)
    weekday = fields.Selection(
        [
            ("MON", "Monday"),
            ("TUE", "Tuesday"),
            ("WED", "Wednesday"),
            ("THU", "Thursday"),
            ("FRI", "Friday"),
            ("SAT", "Saturday"),
            ("SUN", "Sunday"),
        ],
        "Weekday",
    )
    byday = fields.Selection(
        [
            ("1", "First"),
            ("2", "Second"),
            ("3", "Third"),
            ("4", "Fourth"),
            ("-1", "Last"),
        ],
        "By Day",
        default="1",
    )

    # Computed field for month-end warning display
    day_warning = fields.Char(compute="_compute_day_warning")

    @api.depends("day")
    def _compute_day_warning(self):
        for rec in self:
            if rec.day and rec.day > 28:
                rec.day_warning = _(
                    "Day %d doesn't exist in all months. Cycles will use the last day of shorter months "
                    "(e.g., Feb 28 instead of Feb %d)."
                ) % (rec.day, rec.day)
            else:
                rec.day_warning = False

    @api.onchange("day")
    def _onchange_day(self):
        """Validate day of month to valid range (1-31)."""
        if self.day and (self.day <= 0 or self.day > 31):
            self.day = 1
            return {
                "warning": {
                    "title": _("Invalid Day of Month"),
                    "message": _("Day of Month must be between 1 and 31. It has been reset to 1."),
                }
            }

    def _check_required_fields(self):
        """Check required fields. Override in inherited models."""
        if not self.name:
            raise UserError(_("Program Name is required."))
        if not self.currency_id:
            raise UserError(_("Currency is required."))

        if self.rrule_type == "monthly" and self.month_by == "day" and not self.byday:
            raise UserError(_("By Day is required when Month By is set to Day of month."))
        if self.rrule_type == "monthly" and self.month_by == "day" and not self.weekday:
            raise UserError(_("Weekday is required when Month By is set to Day of month."))
        if self.rrule_type == "monthly" and self.month_by == "date" and not self.day:
            raise UserError(_("Day of Month is required when Month By is set to Date of month."))
        if self.rrule_type == "weekly" and not any(
            [self.mon, self.tue, self.wed, self.thu, self.fri, self.sat, self.sun]
        ):
            raise UserError(_("At least one day of the week must be selected."))

        # Check for duplicate program name
        existing_program = self.env["spp.program"].search([("name", "=", self.name)], limit=1)
        if existing_program:
            raise UserError(_("A program with this name already exists. Program names must be unique."))
        return True

    def _get_recurrent_field_values(self):
        """Get recurrent field values for calendar.recurrence."""
        return {
            "byday": self.byday,
            "month_by": self.month_by,
            "mon": self.mon,
            "tue": self.tue,
            "wed": self.wed,
            "thu": self.thu,
            "fri": self.fri,
            "sat": self.sat,
            "sun": self.sun,
            "day": self.day,
            "weekday": self.weekday,
        }

    def _generate_unique_journal_code(self, name):
        """Generate a unique journal code based on the name.

        Journal codes in Odoo are limited to 5 characters.
        This method generates a base code from the name and appends
        a number suffix if the code already exists.
        """
        journal_obj = self.env["account.journal"]
        base_code = name[:3].upper() if len(name) >= 3 else name.upper()

        # Check if base code is available
        if not journal_obj.search([("code", "=", base_code)], limit=1):
            return base_code

        # Try with numeric suffix (1-99)
        for i in range(1, 100):
            suffix = str(i)
            # Keep total length <= 5 chars
            prefix_len = 5 - len(suffix)
            candidate = base_code[:prefix_len] + suffix
            if not journal_obj.search([("code", "=", candidate)], limit=1):
                return candidate

        # Fallback: use timestamp-based suffix
        import time

        return base_code[:2] + str(int(time.time()))[-3:]

    def create_journal(self, name, currency_id):
        """Create journal for program."""
        journal_obj = self.env["account.journal"]
        journal = journal_obj.search([("name", "=", name), ("currency_id", "=", currency_id)], limit=1)
        if not journal:
            journal = journal_obj.create(
                {
                    "name": name,
                    "code": self._generate_unique_journal_code(name),
                    "type": "bank",
                    "currency_id": currency_id,
                }
            )
        return journal.id

    def _get_entitlement_manager(self, program_id):
        """Get entitlement manager. Override in inherited models."""
        raise UserError(f"DEBUG BASE CLASS: Entitlement Type = '{self.entitlement_type}' | This should be overridden!")


class SPPCreateNewProgramWiz(models.TransientModel):
    _inherit = "spp.program.create.wizard"

    @api.model
    def _get_admin_area_domain(self):
        return [("area_type_id", "=", self.env.ref("spp_area.admin_area_type").id)]

    @api.model
    def _default_warehouse_id(self):
        return self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)

    admin_area_ids = fields.Many2many("spp.area", domain=_get_admin_area_domain)

    is_one_time_distribution = fields.Boolean("One-time Distribution")

    # In-Kind Entitlement Manager fields
    is_evaluate_single_item = fields.Boolean("Evaluate one item", default=False)
    entitlement_item_ids = fields.One2many(
        "spp.program.create.wizard.entitlement.item", "program_id", "Entitlement Items"
    )

    # Inventory integration fields
    manage_inventory = fields.Boolean(default=False)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        default=_default_warehouse_id,
        check_company=True,
    )
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    # SQL-base Eligibility Manager
    eligibility_type = fields.Selection(
        [("default_eligibility", "Default")],
        "Eligibility Manager",
        default="default_eligibility",
    )

    id_type_id = fields.Many2one("spp.id.type", "ID Type to store in entitlements")
    view_id = fields.Many2one(
        "ir.ui.view",
        "Program UI Template",
        domain="[('model', '=', 'spp.program'), ('type', '=', 'form'),('inherit_id', '=', False),]",
        default=lambda self: self._get_default_program_ui(),
    )

    cycle_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        "Cycle Approval Definition",
        domain="[('model_id.model', '=', 'spp.cycle')]",
        default=lambda self: self._get_default_cycle_approval_definition(),
        required=True,
    )

    entitlement_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        "Entitlement Approval Definition",
        compute="_compute_entitlement_approval_definition_domain",
        store=True,
        readonly=False,
        required=True,
        default=lambda self: self._get_default_entitlement_approval_definition(),
    )

    step2_ready = fields.Boolean(compute="_compute_step2_ready")

    @api.depends("entitlement_type", "entitlement_cash_item_ids", "entitlement_item_ids")
    def _compute_step2_ready(self):
        """True when the entitlement section has at least one configured item."""
        for rec in self:
            if rec.entitlement_type == "cash":
                rec.step2_ready = bool(rec.entitlement_cash_item_ids)
            elif rec.entitlement_type == "inkind":
                rec.step2_ready = bool(rec.entitlement_item_ids)
            else:
                rec.step2_ready = True

    def _get_default_cycle_approval_definition(self):
        return self.env.ref("spp_programs.approval_definition_cycle")

    def _get_default_entitlement_approval_definition(self):
        return self.env.ref("spp_programs.approval_definition_entitlement")

    @api.depends("entitlement_type")
    def _compute_entitlement_approval_definition_domain(self):
        """Set the appropriate approval definition based on entitlement type."""
        for rec in self:
            # Always update when entitlement type changes
            if rec.entitlement_type == "inkind":
                inkind_def = self.env.ref(
                    "spp_programs.approval_definition_entitlement_inkind",
                    raise_if_not_found=False,
                )
                if inkind_def:
                    rec.entitlement_approval_definition_id = inkind_def
                else:
                    # Fallback to cash approval definition if in-kind not found
                    rec.entitlement_approval_definition_id = self.env.ref(
                        "spp_programs.approval_definition_entitlement",
                        raise_if_not_found=False,
                    )
            else:
                # For 'default' and 'cash' entitlement types
                rec.entitlement_approval_definition_id = self.env.ref(
                    "spp_programs.approval_definition_entitlement",
                    raise_if_not_found=False,
                )

    def _get_default_program_ui(self):
        return self.env.ref("spp_programs.view_program_list_form")

    @api.onchange("admin_area_ids")
    def on_admin_area_ids_change(self):
        eligibility_domain = self.eligibility_domain
        domain = []
        if eligibility_domain not in [None, "[]"]:
            # Do not remove other filters
            # Convert the string to list of tuples
            domain = ast.literal_eval(eligibility_domain)
            # get the area_center_id from the list
            area_dom = [flt for flt in domain if "area_id" in flt]
            if area_dom:
                domain.remove(area_dom[0])

        if self.admin_area_ids:
            area_ids = self.admin_area_ids.ids
            domain.append(("area_id", "in", tuple(area_ids)))
        eligibility_domain = str(self._insert_domain_operator(domain))

        self.eligibility_domain = eligibility_domain

    def _insert_domain_operator(self, domain):
        """Insert operator to the domain"""
        if not domain:
            return domain
        operator_used = AND
        if domain[0] == "|":
            operator_used = OR
        new_domain = []
        domain = list(filter(lambda a: a not in ["&", "|", "!"], domain))
        for dom in domain:
            new_domain = operator_used([new_domain, [dom]])
        return new_domain

    def create_program(self):
        self.ensure_one()
        self._check_required_fields()

        program_vals = self.get_program_vals()
        program = self.env["spp.program"].with_context(skip_default_managers=True).create(program_vals)

        program_id = program.id
        vals = {}

        # Set Default Eligibility Manager settings
        vals.update(self._get_eligibility_manager(program_id))

        # Set Default Cycle Manager settings
        # Add a new record to default cycle manager model

        cycle_manager_default_val = self.get_cycle_manager_default_val(program_id)
        def_mgr = self.env["spp.cycle.manager.default"].create(cycle_manager_default_val)

        # Add a new record to cycle manager parent model

        cycle_manager_val = self.get_cycle_manager_val(program_id, def_mgr)
        mgr = self.env["spp.cycle.manager"].create(cycle_manager_val)

        vals.update({"cycle_manager_ids": [(4, mgr.id)]})

        # Set Default Entitlement Manager
        vals.update(self._get_entitlement_manager(program_id))

        # Set Default Program Manager
        vals.update(self._get_program_manager(program_id))

        # Clean legacy aliases that are not real fields on spp.program
        vals.pop("eligibility_managers", None)
        vals.pop("cycle_managers", None)
        # Convert legacy entitlement_managers key to entitlement_manager_ids
        if "entitlement_managers" in vals:
            entitlement_managers = vals.pop("entitlement_managers")
            if "entitlement_manager_ids" not in vals:
                vals["entitlement_manager_ids"] = entitlement_managers

        vals.update({"is_one_time_distribution": self.is_one_time_distribution})

        # Complete the program data
        program.update(vals)

        if self.import_beneficiaries == "yes" or self.is_one_time_distribution:
            self.program_wizard_import_beneficiaries(program)

        if self.is_one_time_distribution:
            program.create_new_cycle()

        view_id = self.env.ref("spp_programs.view_program_list_form")
        if self.view_id:
            view_id = self.view_id

        program.view_id = view_id.id

        # Close modal and open program form using client action with async/await
        return {
            "type": "ir.actions.client",
            "tag": "open_program_close_modal",
            "params": {
                "program_id": program_id,
                "name": _("Program"),
                "view_id": view_id.id,
            },
        }

    def _get_default_eligibility_manager_val(self, program_id):
        return {
            "name": "Default",
            "program_id": program_id,
            "admin_area_ids": self.admin_area_ids,
            "eligibility_domain": self.eligibility_domain,
        }

    def _get_eligibility_managers_val(self, program_id, def_mgr):
        return {
            "program_id": program_id,
            "manager_ref_id": f"{def_mgr._name},{str(def_mgr.id)}",
        }

    def _get_eligibility_manager(self, program_id):
        val = {}
        if self.eligibility_type == "default_eligibility":
            # Add a new record to default eligibility manager model
            default_eligibility_manager_val = self._get_default_eligibility_manager_val(program_id)
            def_mgr = self.env["spp.program.membership.manager.default"].create(default_eligibility_manager_val)

            # Add a new record to eligibility manager parent model
            eligibility_manager_val = self._get_eligibility_managers_val(program_id, def_mgr)
            mgr = self.env["spp.eligibility.manager"].create(eligibility_manager_val)

            val = {
                "eligibility_manager_ids": [(4, mgr.id)],
                # Backward-compat for tests expecting legacy key
                "eligibility_managers": [(4, mgr.id)],
            }
        return val

    def program_wizard_import_beneficiaries(self, program):
        eligibility_managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        eligibility_managers[0].import_eligible_registrants(state="enrolled")

    def get_cycle_manager_val(self, program_id, cycle_manager_default):
        return {
            "program_id": program_id,
            "manager_ref_id": f"{cycle_manager_default._name},{str(cycle_manager_default.id)}",
        }

    def get_cycle_manager_default_val(self, program_id):
        return {
            "name": "Default",
            "program_id": program_id,
            "auto_approve_entitlements": self.auto_approve_entitlements,
            "cycle_duration": self.cycle_duration,
            "rrule_type": self.rrule_type,
            "approver_group_id": self.approver_group_id.id or None,
            "approval_definition_id": self.cycle_approval_definition_id.id or None,
            **self._get_recurrent_field_values(),
        }

    def get_program_vals(self):
        # Create a new journal for this program
        journal_id = self.create_journal(self.name, self.currency_id.id)

        return {
            "name": self.name,
            "currency_id": self.currency_id.id,
            "journal_id": journal_id,
            "target_type": self.target_type,
        }

    def _reopen_self(self):
        return {
            "name": "Create Program",
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def next_step(self):
        """Move to the next step in the wizard."""
        self.ensure_one()
        if self.state == "step1":
            # Validate step 1 fields
            if not self.name:
                raise UserError(_("Please enter a program name."))
            if not self.currency_id:
                raise UserError(_("Please select a currency."))
            # Check for duplicate program name
            existing_program = self.env["spp.program"].search([("name", "=", self.name)], limit=1)
            if existing_program:
                raise UserError(_("A program with this name already exists. Program names must be unique."))
            self.state = "step2"
        return self._reopen_self()

    def prev_step(self):
        """Move to the previous step in the wizard."""
        self.ensure_one()
        if self.state == "step2":
            self.state = "step1"
        return self._reopen_self()

    def _check_required_fields(self):
        res = super()._check_required_fields()
        if self.entitlement_type == "cash" and not self.entitlement_cash_item_ids:
            raise UserError(
                _(
                    "No amount defined for the selected benefit type (Cash). Please add at least one "
                    "Cash Entitlement Item with a valid amount under the 'What Do They Receive' tab."
                )
            )
        if self.entitlement_type == "inkind":
            if not self.entitlement_item_ids:
                raise UserError(
                    _(
                        "No items defined for the selected benefit type (In-Kind). Please add at least one "
                        "In-Kind Entitlement Item with a valid quantity under the 'What Do They Receive' tab."
                    )
                )
            if self.manage_inventory and not self.warehouse_id:
                raise UserError(
                    _("For inventory management, the warehouse is required in the In-kind entitlement manager.")
                )
        return res

    def _get_entitlement_manager(self, program_id):
        val = {}
        if self.entitlement_type == "cash":
            # Add a new record to cash entitlement manager model
            entitlement_item_ids = []
            for item in self.entitlement_cash_item_ids:
                entitlement_item_ids.append(
                    [
                        0,
                        0,
                        {
                            "sequence": item.sequence,
                            "amount": item.amount,
                            "currency_id": item.currency_id.id,
                            "condition": item.condition,
                            "multiplier_field": item.multiplier_field.id,
                            "max_multiplier": item.max_multiplier,
                        },
                    ]
                )

            def_mgr_obj = "spp.program.entitlement.manager.cash"
            def_mgr = self.env[def_mgr_obj].create(
                {
                    "name": "Cash",
                    "program_id": program_id,
                    "is_evaluate_one_item": self.is_evaluate_one_item,
                    "entitlement_item_ids": entitlement_item_ids,
                    "max_amount": self.max_amount,
                    "entitlement_validation_group_id": self.entitlement_validation_group_id.id,
                    "id_type_id": self.id_type_id.id,
                    "approval_definition_id": self.entitlement_approval_definition_id.id or None,
                }
            )

            # Add a new record to entitlement manager parent model
            man_obj = self.env["spp.program.entitlement.manager"]
            mgr = man_obj.create(
                {
                    "program_id": program_id,
                    "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
                }
            )
            val = {"entitlement_manager_ids": [(4, mgr.id)]}
        elif self.entitlement_type == "inkind":
            # Add a new record to in-kind entitlement manager model
            entitlement_item_ids = []
            for item in self.entitlement_item_ids:
                entitlement_item_ids.append(
                    [
                        0,
                        0,
                        {
                            "sequence": item.sequence,
                            "product_id": item.product_id.id,
                            "quantity": item.quantity,
                            "condition": item.condition,
                            "multiplier_field": item.multiplier_field.id,
                            "max_multiplier": item.max_multiplier,
                        },
                    ]
                )

            def_mgr_obj = "spp.program.entitlement.manager.inkind"
            def_mgr = self.env[def_mgr_obj].create(
                {
                    "name": "In-kind",
                    "program_id": program_id,
                    "is_evaluate_single_item": self.is_evaluate_single_item,
                    "entitlement_item_ids": entitlement_item_ids,
                    "entitlement_validation_group_id": self.entitlement_validation_group_id.id,
                    "id_type_id": self.id_type_id.id,
                    "manage_inventory": self.manage_inventory,
                    "warehouse_id": self.warehouse_id.id,
                    "approval_definition_id": self.entitlement_approval_definition_id.id or None,
                }
            )

            # Add a new record to entitlement manager parent model
            man_obj = self.env["spp.program.entitlement.manager"]
            mgr = man_obj.create(
                {
                    "program_id": program_id,
                    "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
                }
            )
            val = {"entitlement_manager_ids": [(4, mgr.id)]}
        return val

    def _get_program_manager(self, program_id):
        """Create the Program Manager which handles enrollment and cycle creation."""
        # Add a new record to default program manager model
        def_mgr_obj = "spp.program.manager.default"
        def_mgr = self.env[def_mgr_obj].create(
            {
                "name": "Default",
                "program_id": program_id,
            }
        )
        # Add a new record to program manager parent model
        mgr = self.env["spp.program.manager"].create(
            {
                "program_id": program_id,
                "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
            }
        )
        return {"program_manager_ids": [(4, mgr.id)]}


class SppCreateProgramWizardCashItem(models.TransientModel):
    _name = "spp.program.create.wizard.entitlement.cash.item"
    _description = "Create a New Program Wizard Entitlement Cash Items"
    _order = "sequence,id"

    sequence = fields.Integer(default=1000)
    program_id = fields.Many2one("spp.program.create.wizard", "New Program", required=True)

    amount = fields.Monetary(
        currency_field="currency_id",
        aggregator="sum",
        default=0.0,
        string="Amount per cycle",
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="program_id.currency_id",
        readonly=True,
    )

    condition = fields.Char("Condition Domain")
    multiplier_field = fields.Many2one(
        "ir.model.fields",
        "Multiplier",
        domain=[("model_id.model", "=", "res.partner"), ("ttype", "=", "integer")],
    )
    max_multiplier = fields.Integer(
        default=0,
        string="Maximum number",
        help="0 means no limit",
    )


class SPPCreateNewProgramWizItem(models.TransientModel):
    _name = "spp.program.create.wizard.entitlement.item"
    _description = "Create a New Program Wizard Entitlement Items"
    _order = "sequence,id"

    sequence = fields.Integer(default=1000)
    program_id = fields.Many2one("spp.program.create.wizard", "New Program", required=True)

    product_id = fields.Many2one("product.product", "Product", domain=[("type", "=", "consu")], required=True)

    condition = fields.Char("Condition Domain")
    multiplier_field = fields.Many2one(
        "ir.model.fields",
        "Multiplier",
        domain=[("model_id.model", "=", "res.partner"), ("ttype", "=", "integer")],
    )
    max_multiplier = fields.Integer(
        default=0,
        string="Maximum number",
        help="0 means no limit",
    )

    quantity = fields.Integer("Quantity", default=1, required=True)
    uom_id = fields.Many2one("uom.uom", "Unit of Measure", related="product_id.uom_id")
