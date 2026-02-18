# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Metric Category - Shared categorization for all metric types."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MetricCategory(models.Model):
    """Categorization for metrics.

    Provides unified category management for all metric types:
    - Statistics (spp.statistic)
    - Simulation metrics (spp.simulation.metric)
    - Future metric types

    Migrated from ``spp.statistic.category`` to provide a shared
    foundation across all metric types.
    """

    _name = "spp.metric.category"
    _description = "Metric Category"
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
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of what metrics belong in this category",
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
    parent_id = fields.Many2one(
        comodel_name="spp.metric.category",
        string="Parent Category",
        ondelete="restrict",
        help="Parent category for hierarchical organization",
    )

    _sql_constraints = [("code_unique", "UNIQUE(code)", "Category code must be unique!")]

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        """Prevent circular parent relationships."""
        if self._has_cycle():
            raise ValidationError(_("You cannot create recursive category hierarchies."))
