"""Pack Installation Wizard for Logic Studio."""

import json
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PackInstallWizard(models.TransientModel):
    """Wizard to install a Logic Pack."""

    _name = "spp.studio.pack.install.wizard"
    _description = "Logic Pack Installation Wizard"

    pack_id = fields.Many2one(
        "spp.studio.pack",
        string="Logic Pack",
        required=True,
        domain=[("state", "=", "available")],
    )

    # Pack info (computed from pack_id)
    pack_name = fields.Char(related="pack_id.name", readonly=True)
    pack_description = fields.Text(related="pack_id.description", readonly=True)

    # Installation options
    install_as_draft = fields.Boolean(
        string="Install as Draft",
        default=True,
        help="Install logic items as Draft for review before publishing",
    )
    install_personas = fields.Boolean(
        string="Install Test Personas",
        default=True,
        help="Include test personas from the pack",
    )

    # Items to install
    item_ids = fields.Many2many(
        "spp.studio.pack.item",
        string="Items to Install",
        compute="_compute_items",
        readonly=False,
        store=True,
    )

    # Variable check results
    missing_variables = fields.Text(
        string="Missing Variables",
        compute="_compute_missing_variables",
    )
    has_missing_variables = fields.Boolean(compute="_compute_missing_variables")

    # Preview fields
    preview_ids = fields.One2many(
        "spp.studio.pack.install.preview",
        "wizard_id",
        string="Preview",
    )
    show_preview = fields.Boolean(
        string="Show Preview",
        default=False,
    )

    # Results
    result_message = fields.Text(string="Result", readonly=True)
    installed_logic_ids = fields.Many2many(
        "spp.cel.expression",
        string="Installed Logic",
        readonly=True,
    )

    @api.depends("pack_id")
    def _compute_items(self):
        """Load items from selected pack."""
        for wizard in self:
            if wizard.pack_id:
                wizard.item_ids = wizard.pack_id.item_ids
            else:
                wizard.item_ids = False

    @api.depends("pack_id", "item_ids")
    def _compute_missing_variables(self):
        """Check which required variables are missing."""
        Variable = self.env["spp.cel.variable"]

        for wizard in self:
            if not wizard.pack_id:
                wizard.missing_variables = ""
                wizard.has_missing_variables = False
                continue

            # Get required variables from pack
            required = wizard.pack_id.required_variable_ids

            # Find which are missing
            missing = []
            for var in required:
                existing = Variable.search([("name", "=", var.name), ("active", "=", True)], limit=1)
                if not existing:
                    missing.append(var.label or var.name)

            if missing:
                wizard.missing_variables = _("Missing variables:\n• ") + "\n• ".join(missing)
                wizard.has_missing_variables = True
            else:
                wizard.missing_variables = _("All required variables are available.")
                wizard.has_missing_variables = False

    def _get_pack_program_id(self):
        """Program id used for constant-value lookups during pack expansion.

        None in the base module. The ``spp_studio_programs`` companion adds a
        ``program_id`` field and returns it here, so program-scoped lookups work
        without ``spp_studio`` depending on ``spp_programs`` (OP#1083).
        """
        return None

    def action_preview(self):
        """Generate preview showing original expressions and runtime resolution preview.

        With deferred resolution, the original expression is stored and variables
        are resolved at evaluation time. This preview shows:
        - Original expression (what will be stored)
        - Runtime preview (what it would resolve to with current variable definitions)
        - Missing variables (variables that need to be defined before logic can run)
        """
        self.ensure_one()

        if not self.pack_id:
            raise UserError(_("Please select a Logic Pack."))

        # Clear existing previews
        self.preview_ids.unlink()

        resolver = self.env["spp.cel.variable.resolver"]

        previews = []
        for item in self.item_ids:
            result = resolver.expand_pack_item(item, program_id=self._get_pack_program_id())

            previews.append(
                Command.create(
                    {
                        "wizard_id": self.id,
                        "item_id": item.id,
                        "item_name": item.name,
                        "expression_type": item.expression_type,
                        "original_expression": result["original_expression"],
                        "expanded_expression": result["expanded_expression"],
                        "missing_variables": ", ".join(result["missing_variables"])
                        if result["missing_variables"]
                        else "",
                        "warnings": "\n".join(result["warnings"]) if result["warnings"] else "",
                    }
                )
            )

        self.write(
            {
                "preview_ids": previews,
                "show_preview": True,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_install(self):
        """Install the selected pack items with original expressions (deferred resolution).

        Variable references are kept in the expression and resolved at evaluation time.
        This allows changes to variable definitions to automatically propagate to all
        logic that uses them.
        """
        self.ensure_one()

        if not self.pack_id:
            raise UserError(_("Please select a Logic Pack to install."))

        if not self.item_ids:
            raise UserError(_("No items selected for installation."))

        Logic = self.env["spp.cel.expression"]

        installed_logic = self.env["spp.cel.expression"]
        installed_personas = self.env["spp.studio.test.persona"]

        # Install each item with ORIGINAL expression (deferred resolution)
        for item in self.item_ids:
            try:
                logic_data = json.loads(item.logic_data)

                # Use the ORIGINAL expression with variable references
                # Variables will be resolved at evaluation time, not installation time
                cel_expression = logic_data.get("cel_expression", "")

                # Determine initial state
                state = "draft" if self.install_as_draft else "published"

                # Create logic record with original expression (variables intact)
                logic_vals = {
                    "name": item.name,
                    "description": item.description or logic_data.get("description"),
                    "expression_type": item.expression_type,
                    # Preserve intended context from pack item
                    "context_type": item.context_type or "individual",
                    "cel_expression": cel_expression,  # Keep original with variable refs
                    "output_type": logic_data.get("output_type", "boolean"),
                    "state": state,
                }

                logic = Logic.create(logic_vals)
                installed_logic |= logic

                # Update pack item reference
                item.installed_logic_id = logic.id

                _logger.info("Installed logic ID %s from pack ID %s", item.id, self.pack_id.id)

            except json.JSONDecodeError as e:
                _logger.error("Invalid JSON in pack item ID %s: %s", item.id, e)
                raise UserError(_("Invalid data in pack item ID %s: %s") % (item.name, e)) from e
            except Exception as e:
                _logger.error("Error installing pack item ID %s: %s", item.id, e)
                raise UserError(_("Error installing '%s': %s") % (item.name, e)) from e

        # Install personas if requested
        if self.install_personas and self.pack_id.persona_ids:
            for persona in self.pack_id.persona_ids:
                new_persona = persona.copy({"is_global": True})
                installed_personas |= new_persona

        # Mark pack as installed
        self.pack_id.write(
            {
                "state": "installed",
                "installed_date": fields.Datetime.now(),
            }
        )

        # Build result message
        message = _("Pack '%s' installed successfully!\n\n") % self.pack_id.name
        message += _("Logic items installed: %d\n") % len(installed_logic)
        if installed_personas:
            message += _("Test personas installed: %d\n") % len(installed_personas)

        if self.install_as_draft:
            message += _("\nAll items installed as Draft. Review and test before publishing.")

        self.result_message = message
        self.installed_logic_ids = installed_logic

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_installed(self):
        """Open list view of installed logic."""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Installed Logic"),
            "res_model": "spp.cel.expression",
            "view_mode": "list,form",
            "domain": [("id", "in", self.installed_logic_ids.ids)],
            "target": "current",
        }


class PackInstallPreview(models.TransientModel):
    """Preview line for pack installation."""

    _name = "spp.studio.pack.install.preview"
    _description = "Pack Install Preview Line"

    wizard_id = fields.Many2one(
        "spp.studio.pack.install.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one(
        "spp.studio.pack.item",
        string="Pack Item",
        readonly=True,
    )
    item_name = fields.Char(string="Item Name", readonly=True)
    description = fields.Text(string="Description", readonly=True)
    expression_type = fields.Selection(
        selection=[
            ("filter", "Filter"),
            ("formula", "Formula"),
            ("scoring", "Scoring"),
            ("validation", "Validation"),
            ("other", "Other"),
        ],
        string="Type",
        readonly=True,
    )
    original_expression = fields.Text(
        string="Original Expression",
        readonly=True,
    )
    expanded_expression = fields.Text(
        string="Expanded Expression",
        help="You can modify this expression before installation",
    )
    missing_variables = fields.Char(
        string="Missing Variables",
        readonly=True,
    )
    warnings = fields.Text(
        string="Warnings",
        readonly=True,
    )
    has_issues = fields.Boolean(
        compute="_compute_has_issues",
        string="Has Issues",
    )

    @api.depends("missing_variables", "warnings")
    def _compute_has_issues(self):
        for rec in self:
            rec.has_issues = bool(rec.missing_variables or rec.warnings)
