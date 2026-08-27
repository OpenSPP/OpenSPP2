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
        groups="base.group_system",
        help=(
            "Python expression for value transformation. "
            "Available variables: value (the source value), and read-only snapshots "
            "of detail and registrant exposing their stored scalar fields only - "
            "no method calls, no relation traversal, no database access - plus "
            "datetime and date. Restricted to system administrators: it is evaluated "
            "server-side and an unevaluable expression blocks the change rather than "
            "writing the raw value."
        ),
    )
