import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HxlTag(models.Model):
    """Registry of HXL hashtags (e.g., #affected, #adm2, #indicator)"""

    _name = "spp.hxl.tag"
    _description = "HXL Hashtag"
    _order = "category, hashtag"

    hashtag = fields.Char(required=True, index=True, help="HXL hashtag, e.g., #affected")
    name = fields.Char(required=True, help="Human-readable name for the hashtag")
    description = fields.Text(help="Detailed description of the hashtag usage")
    category = fields.Selection(
        [
            ("geographic", "Geographic"),
            ("population", "Population & Caseload"),
            ("organization", "Organizations"),
            ("activity", "Activities & Sectors"),
            ("indicator", "Indicators"),
            ("metadata", "Metadata"),
            ("item", "Items & Commodities"),
            ("value", "Values"),
            ("date", "Date & Time"),
            ("openspp", "OpenSPP Custom"),
        ],
        help="Category for organizing hashtags",
    )
    is_standard = fields.Boolean(default=True, help="True if part of HXL 1.1 standard specification")
    data_type = fields.Selection(
        [
            ("text", "Text"),
            ("number", "Number"),
            ("date", "Date"),
            ("geo", "Geographic"),
        ],
        default="text",
        help="Expected data type for this hashtag",
    )
    active = fields.Boolean(default=True)

    _hashtag_unique = models.Constraint("unique(hashtag)", "HXL hashtag must be unique!")

    @api.constrains("hashtag")
    def _check_hashtag_format(self):
        """Ensure hashtag starts with # and contains only valid characters"""
        for rec in self:
            if rec.hashtag:
                if not rec.hashtag.startswith("#"):
                    raise ValidationError(_("HXL hashtag must start with #"))
                # Check for valid characters (alphanumeric, underscore, dash after #)
                tag_part = rec.hashtag[1:]
                if not tag_part or not all(c.isalnum() or c in "_-" for c in tag_part):
                    raise ValidationError(
                        _("HXL hashtag can only contain alphanumeric characters, underscore, and dash")
                    )
