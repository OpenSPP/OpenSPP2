import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HxlAttribute(models.Model):
    """Registry of HXL attributes (e.g., +f, +children, +code)"""

    _name = "spp.hxl.attribute"
    _description = "HXL Attribute"
    _order = "category, code"

    code = fields.Char(required=True, index=True, help="Attribute code, e.g., +f, +children")
    name = fields.Char(required=True, help="Human-readable name for the attribute")
    description = fields.Text(help="Detailed description of the attribute usage")
    category = fields.Selection(
        [
            ("gender", "Gender"),
            ("age", "Age Group"),
            ("population_type", "Population Type"),
            ("data_type", "Data Type"),
            ("role", "Organizational Role"),
            ("geographic", "Geographic"),
            ("vocabulary", "Vocabulary Reference"),
            ("language", "Language"),
            ("openspp", "OpenSPP Custom"),
        ],
        help="Category for organizing attributes",
    )
    is_standard = fields.Boolean(default=True, help="True if part of HXL 1.1 standard specification")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint("unique(code)", "HXL attribute code must be unique!")

    @api.constrains("code")
    def _check_code_format(self):
        """Ensure attribute code starts with + and contains only valid characters"""
        for rec in self:
            if rec.code:
                if not rec.code.startswith("+"):
                    raise ValidationError(_("HXL attribute code must start with +"))
                # Check for valid characters (alphanumeric, underscore, dash after +)
                code_part = rec.code[1:]
                if not code_part or not all(c.isalnum() or c in "_-" for c in code_part):
                    raise ValidationError(
                        _("HXL attribute code can only contain alphanumeric characters, underscore, and dash")
                    )
