# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Metric Base - Unified foundation for all metric types."""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MetricBase(models.AbstractModel):
    """Shared foundation for all metric types.

    Provides genuinely shared fields that concrete metrics inherit without overriding:
    - Identity (name, label, description)
    - Presentation (unit, decimal_places)
    - Categorization (category_id)
    - Metadata (active, sequence)

    Computation-specific fields (metric_type, cel_expression, aggregation, format)
    are defined by concrete models since they vary incompatibly between types.

    Usage
    -----
    Concrete models inherit this to avoid field duplication:

        class Statistic(models.Model):
            _name = "spp.statistic"
            _inherit = ["spp.metric.base"]

            # Add statistic-specific fields
            variable_id = fields.Many2one(...)
            format = fields.Selection([("count", "Count"), ...])
            is_published_gis = fields.Boolean()
            ...

        class SimulationMetric(models.Model):
            _name = "spp.simulation.metric"
            _inherit = ["spp.metric.base"]

            # Add simulation-specific fields
            metric_type = fields.Selection([("aggregate", "Aggregate"), ...])
            cel_expression = fields.Text(...)
            aggregation = fields.Selection(...)
            ...
    """

    _name = "spp.metric.base"
    _description = "Metric Base Model"

    # ─── Identity ───────────────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        help="Technical identifier (e.g., 'children_under_5')",
    )
    label = fields.Char(
        string="Label",
        required=True,
        translate=True,
        help="Human-readable display label (e.g., 'Children Under 5')",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Detailed description of what this metric measures",
    )

    # ─── Presentation ───────────────────────────────────────────────────
    unit = fields.Char(
        string="Unit",
        help="Unit of measurement (e.g., 'people', 'USD', '%')",
    )

    decimal_places = fields.Integer(
        string="Decimal Places",
        default=0,
        help="Decimal places for display",
    )

    # ─── Categorization ─────────────────────────────────────────────────
    category_id = fields.Many2one(
        comodel_name="spp.metric.category",
        string="Category",
        ondelete="restrict",
        help="Category for organizing metrics in displays",
    )

    # ─── Flags ──────────────────────────────────────────────────────────
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive metrics are hidden",
    )

    # ─── Metadata ───────────────────────────────────────────────────────
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order within category",
    )
