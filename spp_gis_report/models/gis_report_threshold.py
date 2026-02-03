import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class GISReportThreshold(models.Model):
    """Color threshold definitions for GIS reports."""

    _name = "spp.gis.report.threshold"
    _description = "GIS Report Color Threshold"
    _order = "sequence"

    report_id = fields.Many2one(
        "spp.gis.report",
        "Report",
        required=True,
        ondelete="cascade",
        index=True,
        help="The report this threshold belongs to",
    )
    sequence = fields.Integer(
        "Sequence",
        default=10,
        help="Display order of thresholds",
    )

    # Threshold range
    min_value = fields.Float(
        "Minimum Value",
        help="Inclusive minimum value. Leave empty for no lower bound.",
    )
    max_value = fields.Float(
        "Maximum Value",
        help="Exclusive maximum value. Leave empty for no upper bound.",
    )

    # Visual representation
    color = fields.Char(
        "Color (Hex)",
        required=True,
        default="#3498db",
        help="Hex color code (e.g., #3498db)",
    )
    label = fields.Char(
        "Label",
        required=True,
        help="Human-readable label (e.g., 'Low', 'Medium', 'High')",
    )
    description = fields.Text(
        "Description",
        help="Detailed description shown in tooltip/legend",
    )
