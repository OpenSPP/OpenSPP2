# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HxlImportMapping(models.Model):
    """Column mapping for import batch.

    Auto-detected during file parsing, can be adjusted by user
    before processing.
    """

    _name = "spp.hxl.import.mapping"
    _description = "HXL Import Column Mapping"
    _order = "batch_id, sequence"

    batch_id = fields.Many2one(
        "spp.hxl.import.batch",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    source_column = fields.Char(
        string="Source Column Header",
        help="Original column header from the file",
    )
    detected_hxl_tag = fields.Char(
        string="Detected HXL Tag",
        help="HXL hashtag detected in the file",
    )

    # What to do with this column
    mapping_type = fields.Selection(
        [
            ("area", "Area Identifier"),
            ("aggregate", "Aggregate Value"),
            ("filter", "Filter Criterion"),
            ("disaggregate", "Disaggregation"),
            ("skip", "Skip"),
        ],
        default="skip",
        required=True,
        help="How this column should be used in the import",
    )

    # Confidence of auto-detection (0.0 to 1.0)
    confidence = fields.Float(
        default=0.0,
        help="Confidence score of automatic mapping (0.0 = low, 1.0 = certain)",
    )

    def name_get(self):
        """Display mapping with context."""
        result = []
        for rec in self:
            name = f"{rec.source_column} [{rec.detected_hxl_tag}] → {rec.mapping_type}"
            result.append((rec.id, name))
        return result
