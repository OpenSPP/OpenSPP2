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
    routing_field = fields.Char(
        help=(
            "For dynamic-approval types, the selectable value this mapping serves. "
            "Defaults to source_field. Set it when one selectable field is applied "
            "through several mappings -- e.g. a name captured as one choice but "
            "stored as separate components -- so apply still writes exactly what "
            "was routed and approved."
        ),
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
            "no method calls, no relation traversal, no database access, and no "
            "group-restricted, binary or reference fields - plus "
            "datetime and date. Restricted to system administrators: it is evaluated "
            "server-side and an unevaluable expression blocks the change rather than "
            "writing the raw value."
        ),
    )
