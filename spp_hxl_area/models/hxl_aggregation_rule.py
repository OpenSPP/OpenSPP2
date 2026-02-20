# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HxlAggregationRule(models.Model):
    """Define how to aggregate HXL data to area indicators.

    Each rule specifies:
    - Which column to aggregate (or count rows)
    - What aggregation function to apply (sum, count, avg, etc.)
    - Optional filter expression to subset rows
    - Optional disaggregation by HXL attributes
    """

    _name = "spp.hxl.aggregation.rule"
    _description = "HXL Aggregation Rule"
    _order = "profile_id, sequence"

    profile_id = fields.Many2one(
        "spp.hxl.import.profile",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        required=True,
        help="Name of the indicator (e.g., 'Severely Damaged Households')",
    )

    # ─── Target Variable ───────────────────────────────────────
    variable_id = fields.Many2one(
        "spp.cel.variable",
        string="Target Variable",
        help="CEL variable to store the aggregated value (for use in expressions)",
    )

    # ─── Aggregation Type ───────────────────────────────────────
    aggregation_type = fields.Selection(
        [
            ("count", "Count Records"),
            ("sum", "Sum Values"),
            ("avg", "Average"),
            ("min", "Minimum"),
            ("max", "Maximum"),
            ("count_distinct", "Count Distinct"),
            ("percentage", "Percentage of Total"),
        ],
        default="count",
        required=True,
        help="How to aggregate the data",
    )

    # ─── Source Configuration ───────────────────────────────────
    source_column_tag = fields.Char(
        string="Source Column HXL Tag",
        help="HXL tag of the column to aggregate (for sum/avg/min/max)",
    )

    filter_expression = fields.Text(
        string="Filter Expression",
        help="Python expression to filter rows (e.g., row.get('severity') == 'severe')",
    )

    # ─── Output Configuration ───────────────────────────────────
    output_hxl_tag = fields.Char(
        string="Output HXL Tag",
        help="HXL tag for re-export (e.g., #affected+hh+severe)",
    )

    # ─── Disaggregation ───────────────────────────────────────
    disaggregate_by_tags = fields.Char(
        string="Disaggregate By",
        help="Comma-separated HXL attributes for disaggregation (e.g., +f,+m,+children)",
    )

    active = fields.Boolean(default=True)

    def name_get(self):
        """Display rule name with profile context."""
        result = []
        for rec in self:
            name = f"{rec.profile_id.code}: {rec.name}"
            result.append((rec.id, name))
        return result
