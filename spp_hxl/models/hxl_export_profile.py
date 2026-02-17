import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HxlExportProfile(models.Model):
    """Pre-configured export templates with HXL tagging"""

    _name = "spp.hxl.export.profile"
    _description = "HXL Export Profile"
    _order = "sequence, name"

    name = fields.Char(required=True, help="Profile name")
    code = fields.Char(
        required=True,
        index=True,
        help="Unique code for the profile, e.g., 'damage_assessment'",
    )
    description = fields.Text(help="Description of the export profile purpose and usage")
    sequence = fields.Integer(default=10, help="Display order")

    # Target model for export
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        help="Target Odoo model for this export profile",
    )
    model_name = fields.Char(related="model_id.model", store=True, string="Model Name")

    # Columns
    column_ids = fields.One2many(
        "spp.hxl.export.profile.column",
        "profile_id",
        string="Columns",
        help="Column definitions for the export",
    )

    # Options
    include_hxl_row = fields.Boolean(default=True, help="Include HXL hashtag row in export (typically row 2)")
    date_format = fields.Char(default="%Y-%m-%d", help="Date format for export (Python strftime format)")

    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("unique(code)", "Export profile code must be unique!")

    @api.constrains("code")
    def _check_code_format(self):
        """Ensure code contains only valid characters"""
        for rec in self:
            if rec.code:
                if not all(c.isalnum() or c in "_-" for c in rec.code):
                    raise ValidationError(
                        _("Profile code can only contain alphanumeric characters, underscore, and dash")
                    )


class HxlExportProfileColumn(models.Model):
    """Column definition within an export profile"""

    _name = "spp.hxl.export.profile.column"
    _description = "HXL Export Profile Column"
    _order = "profile_id, sequence"

    profile_id = fields.Many2one(
        "spp.hxl.export.profile",
        required=True,
        ondelete="cascade",
        string="Profile",
        help="Parent export profile",
    )
    sequence = fields.Integer(default=10, help="Display order")

    # Column definition
    name = fields.Char(required=True, help="Column header name (human-readable)")
    field_path = fields.Char(required=True, help="Dot notation field path (e.g., 'partner_id.name')")

    # HXL tagging
    hxl_tag = fields.Char(
        help="Manual HXL tag entry (e.g., '#affected+children'). If set, overrides hashtag/attributes."
    )
    hxl_hashtag_id = fields.Many2one("spp.hxl.tag", string="Hashtag", help="Select HXL hashtag from registry")
    hxl_attribute_ids = fields.Many2many(
        "spp.hxl.attribute",
        string="Attributes",
        help="Select HXL attributes to combine with hashtag",
    )

    # Computed full tag
    computed_hxl_tag = fields.Char(
        compute="_compute_hxl_tag",
        store=True,
        string="HXL Tag",
        help="Computed full HXL tag combining hashtag and attributes",
    )

    active = fields.Boolean(default=True)

    @api.depends("hxl_tag", "hxl_hashtag_id", "hxl_attribute_ids")
    def _compute_hxl_tag(self):
        """Compute the full HXL tag from components or manual entry"""
        for rec in self:
            if rec.hxl_tag:
                # Manual entry takes precedence
                rec.computed_hxl_tag = rec.hxl_tag
            elif rec.hxl_hashtag_id:
                # Build from hashtag + attributes
                tag = rec.hxl_hashtag_id.hashtag
                for attr in rec.hxl_attribute_ids.sorted("code"):
                    tag += attr.code
                rec.computed_hxl_tag = tag
            else:
                rec.computed_hxl_tag = False
