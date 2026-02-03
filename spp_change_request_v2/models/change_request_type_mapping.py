from odoo import fields, models


class SPPChangeRequestTypeMapping(models.Model):
    """Mapping from detail fields to registrant fields for apply."""

    _name = "spp.change.request.type.mapping"
    _description = "Change Request Apply Mapping"
    _order = "sequence"

    type_id = fields.Many2one(
        "spp.change.request.type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    source_field = fields.Char(
        required=True,
        help="Field name on detail model",
    )
    target_field = fields.Char(
        required=True,
        help="Field name on registrant (res.partner)",
    )
    transform = fields.Selection(
        [
            ("direct", "Direct Copy"),
            ("expression", "Expression"),
        ],
        default="direct",
    )
    transform_expression = fields.Char(
        help=(
            "Python expression for value transformation. "
            "Available variables: value, detail, registrant, datetime, date. "
            "WARNING: Only administrators should configure expressions - "
            "arbitrary code execution risk."
        ),
    )
