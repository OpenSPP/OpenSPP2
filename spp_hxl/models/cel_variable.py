import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CELVariableHxl(models.Model):
    """Extend CEL Variable with HXL mapping fields"""

    _inherit = "spp.cel.variable"

    # HXL Mapping
    hxl_hashtag = fields.Char(
        string="HXL Hashtag",
        help="Primary HXL hashtag, e.g., #affected",
    )
    hxl_attributes = fields.Char(
        string="HXL Attributes",
        help="HXL attributes, e.g., +f+children",
    )
    hxl_tag = fields.Char(
        string="HXL Tag",
        compute="_compute_hxl_tag",
        store=True,
        help="Full HXL tag, e.g., #affected+f+children",
    )

    # Import behavior
    hxl_import_action = fields.Selection(
        [
            ("field", "Map to Model Field"),
            ("event", "Create Event Data"),
            ("variable", "Store as Cached Variable"),
            ("skip", "Skip on Import"),
        ],
        string="HXL Import Action",
        default="variable",
        help="How to handle this variable when importing HXL-tagged data",
    )

    # Export behavior
    hxl_export_include = fields.Boolean(
        string="Include in HXL Export",
        default=True,
        help="Include this variable in HXL-tagged exports",
    )

    @api.depends("hxl_hashtag", "hxl_attributes")
    def _compute_hxl_tag(self):
        """Compute the full HXL tag from hashtag and attributes"""
        for rec in self:
            if rec.hxl_hashtag:
                # Ensure hashtag starts with #
                hashtag = rec.hxl_hashtag if rec.hxl_hashtag.startswith("#") else f"#{rec.hxl_hashtag}"
                rec.hxl_tag = hashtag + (rec.hxl_attributes or "")
            else:
                rec.hxl_tag = False
