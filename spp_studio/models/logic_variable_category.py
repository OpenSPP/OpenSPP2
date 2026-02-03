# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Logic Variable Category - UI extension for CEL Variable Category.

This module extends spp.cel.variable.category with UI-specific features:
- Icons and colors for visual organization
- Hierarchical structure (parent/child categories)
- Enhanced name display
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LogicVariableCategory(models.Model):
    """UI Extension for CEL Variable Category.

    Extends spp.cel.variable.category with Studio-specific features
    while keeping the same database table.
    """

    _inherit = "spp.cel.variable.category"
    _name = "spp.cel.variable.category"  # Keep same table
    _description = "Variable Category"
    _order = "sequence, name"
    _parent_store = True

    # ═══════════════════════════════════════════════════════════════════════
    # UI FIELDS (not in core spp.cel.variable.category)
    # ═══════════════════════════════════════════════════════════════════════

    icon = fields.Char(
        string="Icon",
        default="fa-folder",
        help="CSS icon class (e.g., 'fa-user', 'fa-home')",
    )
    color = fields.Char(
        string="Color",
        help="UI color for visual grouping (e.g., '#3498db')",
    )

    # Hierarchical structure
    parent_id = fields.Many2one(
        comodel_name="spp.cel.variable.category",
        string="Parent Category",
        ondelete="cascade",
        help="Parent category for hierarchical organization",
    )
    parent_path = fields.Char(
        string="Parent Path",
        index=True,
        help="Internal field for hierarchical queries",
    )
    child_ids = fields.One2many(
        comodel_name="spp.cel.variable.category",
        inverse_name="parent_id",
        string="Subcategories",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        """Prevent circular parent references."""
        if not self._check_recursion():
            raise ValidationError(_("Error! You cannot create recursive categories."))

    # ═══════════════════════════════════════════════════════════════════════
    # DISPLAY METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def name_get(self):
        """Return name with hierarchical path and variable count.

        Returns:
            list: List of (id, name) tuples
        """
        result = []
        for rec in self:
            # Build hierarchical name if parent exists
            if rec.parent_id:
                name = f"{rec.parent_id.name} / {rec.name}"
            else:
                name = rec.name

            # Add variable count
            if rec.variable_count:
                name = f"{name} ({rec.variable_count})"

            result.append((rec.id, name))
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_view_variables(self):
        """Open list of variables in this category.

        Returns:
            dict: Action to open variable list
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Variables: %s") % self.name,
            "res_model": "spp.cel.variable",
            "view_mode": "list,form",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id},
        }
