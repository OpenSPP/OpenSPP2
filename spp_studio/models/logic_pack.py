"""Studio Package models for bundled expression distribution."""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LogicPack(models.Model):
    """Pre-built packages of expressions for common use cases."""

    _name = "spp.studio.pack"
    _description = "Studio Package"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(
        string="Code",
        required=True,
        help="Unique identifier for this pack",
    )
    description = fields.Text(string="Description", translate=True)

    # Contents
    item_ids = fields.One2many(
        "spp.studio.pack.item",
        "pack_id",
        string="Logic Items",
    )
    persona_ids = fields.Many2many(
        "spp.studio.test.persona",
        "spp_studio_pack_persona_rel",
        "pack_id",
        "persona_id",
        string="Test Personas",
    )

    # Requirements
    required_variable_ids = fields.Many2many(
        "spp.cel.variable",
        "spp_studio_pack_variable_rel",
        "pack_id",
        "variable_id",
        string="Required Variables",
        help="Variables that must exist for this pack to work",
    )
    required_modules = fields.Char(
        string="Required Modules",
        help="Comma-separated module names required for this pack",
    )

    # Metadata
    version = fields.Char(string="Version", default="1.0")
    author = fields.Char(string="Author")
    category = fields.Selection(
        [
            ("cash_transfer", "Cash Transfer"),
            ("food_security", "Food Security"),
            ("education", "Education"),
            ("health", "Health"),
            ("emergency", "Emergency Response"),
            ("social_pension", "Social Pension"),
            ("child_benefit", "Child Benefit"),
            ("disability", "Disability Support"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
    )
    sequence = fields.Integer(string="Sequence", default=10)

    # Installation state
    state = fields.Selection(
        [
            ("available", "Available"),
            ("installed", "Installed"),
        ],
        string="Status",
        default="available",
    )
    installed_date = fields.Datetime(string="Installed Date", readonly=True)

    # Computed
    item_count = fields.Integer(compute="_compute_item_count")
    missing_variable_count = fields.Integer(compute="_compute_missing_variables")

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure pack code is unique."""
        for rec in self:
            if rec.code:
                duplicate = self.search_count(
                    [
                        ("code", "=", rec.code),
                        ("id", "!=", rec.id),
                    ]
                )
                if duplicate:
                    raise ValidationError(_("Pack code '%s' already exists.") % rec.code)

    @api.depends("item_ids")
    def _compute_item_count(self):
        for pack in self:
            pack.item_count = len(pack.item_ids)

    @api.depends("required_variable_ids")
    def _compute_missing_variables(self):
        Variable = self.env["spp.cel.variable"]
        for pack in self:
            missing = 0
            for var in pack.required_variable_ids:
                if not Variable.search([("name", "=", var.name), ("active", "=", True)], limit=1):
                    missing += 1
            pack.missing_variable_count = missing

    def action_install(self):
        """Open installation wizard."""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Install Pack: %s") % self.name,
            "res_model": "spp.studio.pack.install.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_pack_id": self.id},
        }

    def action_uninstall(self):
        """Reset pack to available (does not delete installed logic)."""
        self.ensure_one()

        self.write(
            {
                "state": "available",
                "installed_date": False,
            }
        )

        # Clear installed references
        for item in self.item_ids:
            item.installed_logic_id = False

        return True

    def action_view_items(self):
        """View pack items."""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Pack Items: %s") % self.name,
            "res_model": "spp.studio.pack.item",
            "view_mode": "tree,form",
            "domain": [("pack_id", "=", self.id)],
        }


class LogicPackItem(models.Model):
    """Individual logic definition within a pack."""

    _name = "spp.studio.pack.item"
    _description = "Logic Pack Item"
    _order = "sequence, id"

    pack_id = fields.Many2one(
        "spp.studio.pack",
        string="Pack",
        required=True,
        ondelete="cascade",
    )

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Sequence", default=10)

    expression_type = fields.Selection(
        [
            ("filter", "Filter"),
            ("formula", "Formula"),
            ("scoring", "Scoring"),
            ("validation", "Data Validation"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="filter",
    )
    context_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Shared"),
        ],
        string="Context",
        default="individual",
        help="Intended evaluation context for this pack item",
    )

    # The logic definition (JSON)
    logic_data = fields.Text(
        string="Logic Data",
        required=True,
        help="JSON containing the logic definition",
    )

    # Post-install reference
    installed_logic_id = fields.Many2one(
        "spp.cel.expression",
        string="Installed Logic",
        readonly=True,
        help="Reference to the installed logic record",
    )
    is_installed = fields.Boolean(
        compute="_compute_is_installed",
        store=True,
    )

    @api.depends("installed_logic_id")
    def _compute_is_installed(self):
        for item in self:
            item.is_installed = bool(item.installed_logic_id)

    @api.constrains("logic_data")
    def _check_logic_data(self):
        """Validate that logic_data is valid JSON."""
        for item in self:
            if item.logic_data:
                try:
                    json.loads(item.logic_data)
                except json.JSONDecodeError as e:
                    raise ValidationError(_("Invalid JSON in logic data for '%s': %s") % (item.name, e)) from e

    def get_logic_dict(self):
        """Return parsed logic data as dictionary."""
        self.ensure_one()
        if self.logic_data:
            try:
                return json.loads(self.logic_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def action_view_installed(self):
        """View the installed logic record."""
        self.ensure_one()

        if not self.installed_logic_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.cel.expression",
            "res_id": self.installed_logic_id.id,
            "view_mode": "form",
        }
