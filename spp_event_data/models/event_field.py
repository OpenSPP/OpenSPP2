# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SPPEventField(models.Model):
    """Field definition for event type (when not using dedicated model)."""

    _name = "spp.event.field"
    _description = "Event Field"
    _order = "sequence, name"

    event_type_id = fields.Many2one("spp.event.type", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, help="Technical name")
    label = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)

    field_type = fields.Selection(
        [
            ("char", "Text"),
            ("text", "Long Text"),
            ("integer", "Integer"),
            ("float", "Decimal"),
            ("boolean", "Yes/No"),
            ("date", "Date"),
            ("datetime", "Date & Time"),
            ("selection", "Selection"),
            ("many2one", "Link"),
        ],
        required=True,
        default="char",
    )

    # Type-specific options
    selection_options = fields.Text(help="JSON array of [value, label] pairs")
    relation_model = fields.Char(help="Model name for many2one fields")

    required = fields.Boolean(default=False)
    help_text = fields.Text(translate=True)

    # Mapping to external source field
    external_field = fields.Char(
        help="Field name in external source (ODK/Kobo)",
    )

    _name_type_uniq = models.Constraint(
        "UNIQUE(event_type_id, name)",
        "Field name must be unique per event type!",
    )
