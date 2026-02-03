# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Variable Category - Core model for organizing variables.

This module provides the base category model for organizing CEL variables.
UI extensions (icon, color, hierarchical structure) are provided by spp_studio.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CELVariableCategory(models.Model):
    """CEL Variable Category - Core organization for variables.

    Categories provide basic grouping for CEL variables:
    - Demographics (income, age, gender)
    - Household (hh_size, dependency_ratio)
    - Characteristics (is_female, is_elderly, is_disabled)
    - Indicators (education_attendance, health_visits)
    - Scoring (pmt_score, vulnerability_index)
    - Program (is_enrolled, cycle_count)

    UI features (icons, colors, hierarchy) are added by spp_studio.
    """

    _name = "spp.cel.variable.category"
    _description = "CEL Variable Category"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Display name (e.g., 'Demographics')",
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Unique technical identifier (e.g., 'demographics')",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive categories are hidden",
    )

    # Variables in this category
    variable_ids = fields.One2many(
        comodel_name="spp.cel.variable",
        inverse_name="category_id",
        string="Variables",
    )
    variable_count = fields.Integer(
        string="Variable Count",
        compute="_compute_variable_count",
        help="Number of variables in this category",
    )

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure category code is unique."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("code", "=", rec.code),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("Category code '%s' already exists.") % rec.code)

    @api.depends("variable_ids")
    def _compute_variable_count(self):
        """Compute number of variables in this category."""
        for rec in self:
            rec.variable_count = len(rec.variable_ids)

    @api.model
    def _get_or_create(self, code, name=None, **kwargs):
        """Get category by code or create if it doesn't exist.

        This is a helper method for the sync process.

        Args:
            code (str): Category code
            name (str, optional): Category name (defaults to code.title())
            **kwargs: Additional field values

        Returns:
            recordset: Category record
        """
        category = self.search([("code", "=", code)], limit=1)

        if not category:
            vals = {
                "code": code,
                "name": name or code.replace("_", " ").title(),
            }
            vals.update(kwargs)
            category = self.create(vals)
            _logger.info("Created new category: %s", code)

        return category
