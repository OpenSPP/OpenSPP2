"""Curated list of string values that should be treated as missing during
scoring (e.g. ``'No Birthdate!'`` returned by computed fields when their
underlying source is empty). Applies globally across every indicator —
each scoring run fetches the active set once and matches every read
field value against it. Toggle ``active`` to retire a sentinel without
losing the audit trail."""

from odoo import fields, models


class SppScoringInvalidValue(models.Model):
    _name = "spp.scoring.invalid.value"
    _description = "Scoring Invalid Value"
    _order = "name"

    name = fields.Char(
        string="Value",
        required=True,
        help="Exact string that should be treated as missing during scoring.",
    )
    description = fields.Char(
        help="Optional note explaining why this value is treated as invalid.",
    )
    active = fields.Boolean(
        default=True,
        help=(
            "Untick to disable this entry without deleting it — useful when "
            "a previously-invalid value should be accepted as real data "
            "going forward."
        ),
    )

    _sql_constraints = [
        (
            "spp_scoring_invalid_value_name_uniq",
            "unique(name)",
            "An invalid-value entry with this string already exists.",
        ),
    ]
