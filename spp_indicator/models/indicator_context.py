# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Statistic Context - Context-specific presentation configuration."""

from odoo import fields, models


class IndicatorContext(models.Model):
    """Context-specific presentation configuration for an indicator.

    Allows overriding default presentation settings for specific contexts
    (GIS, dashboard, API, reports). For example, an indicator might use
    a different label or grouping in the GIS context vs. dashboard.
    """

    _name = "spp.indicator.context"
    _description = "Indicator Context Configuration"
    _order = "statistic_id, context"

    statistic_id = fields.Many2one(
        comodel_name="spp.indicator",
        string="Indicator",
        required=True,
        ondelete="cascade",
    )

    context = fields.Selection(
        selection=[
            ("gis", "GIS / QGIS"),
            ("dashboard", "Dashboard"),
            ("api", "External API"),
            ("report", "Reports / Export"),
        ],
        string="Context",
        required=True,
        help="The context this configuration applies to",
    )

    # ─── Presentation Overrides ─────────────────────────────────────────
    label = fields.Char(
        string="Label Override",
        translate=True,
        help="Override the default label for this context",
    )
    format = fields.Selection(
        selection=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("avg", "Average"),
            ("percent", "Percentage"),
            ("ratio", "Ratio"),
            ("currency", "Currency"),
        ],
        string="Format Override",
        help="Override the default format for this context",
    )
    group = fields.Char(
        string="Group Override",
        help="Override the category grouping for this context",
    )

    # ─── Privacy Override ────────────────────────────────────────────────
    minimum_count = fields.Integer(
        string="Minimum Count Override",
        help="Override the minimum count threshold for this context. "
        "Use higher values for public-facing contexts (e.g., 10 for GIS maps) "
        "and lower values for internal dashboards (e.g., 5). "
        "Leave empty to use the statistic's default.",
    )

    # ─── Context-specific Fields ────────────────────────────────────────
    icon = fields.Char(
        string="Icon",
        help="Icon for this context (Font Awesome class)",
    )
    color = fields.Char(
        string="Color",
        help="Color for this context (hex code)",
    )

    # GIS-specific
    gis_threshold_mode = fields.Selection(
        selection=[
            ("auto_quartile", "Auto - Quartiles"),
            ("auto_equal", "Auto - Equal Intervals"),
            ("auto_jenks", "Auto - Natural Breaks"),
            ("manual", "Manual Thresholds"),
        ],
        string="GIS Threshold Mode",
        help="How to calculate color thresholds for GIS visualization",
    )

    # Dashboard-specific
    dashboard_widget_type = fields.Selection(
        selection=[
            ("number", "Number"),
            ("gauge", "Gauge"),
            ("chart", "Chart"),
        ],
        string="Dashboard Widget",
        help="Type of widget to use in dashboards",
    )

    _statistic_context_unique = models.Constraint(
        "UNIQUE(statistic_id, context)",
        "Each statistic can only have one configuration per context.",
    )
