from odoo import fields, models


class SppScoringResultDetail(models.Model):
    """Per-indicator breakdown for a scoring result."""

    _name = "spp.scoring.result.detail"
    _description = "Scoring Result Detail"
    _order = "sequence, id"

    result_id = fields.Many2one(
        comodel_name="spp.scoring.result",
        string="Scoring Result",
        required=True,
        ondelete="cascade",
    )
    indicator_id = fields.Many2one(
        comodel_name="spp.scoring.indicator",
        string="Indicator",
        required=True,
        ondelete="restrict",
    )
    sequence = fields.Integer(
        string="Sequence",
        related="indicator_id.sequence",
        store=True,
    )

    # Values
    field_value = fields.Char(
        string="Field Value",
        help="The raw value read from the registrant",
    )
    indicator_score = fields.Float(
        string="Indicator Score",
        help="Score before weight is applied",
    )
    weight = fields.Float(
        string="Weight",
        related="indicator_id.weight",
    )
    weighted_score = fields.Float(
        string="Weighted Score",
        help="indicator_score * weight",
    )

    # Status
    has_error = fields.Boolean(
        string="Has Error",
        default=False,
    )
    notes = fields.Char(
        string="Notes",
        help="Error message or other notes",
    )

    # Display helpers
    indicator_name = fields.Char(
        related="indicator_id.name",
        string="Indicator Name",
    )
    indicator_code = fields.Char(
        related="indicator_id.code",
        string="Indicator Code",
    )
