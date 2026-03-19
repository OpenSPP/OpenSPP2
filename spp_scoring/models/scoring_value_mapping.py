from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SppScoringValueMapping(models.Model):
    """Maps field values to scores for mapped/range indicators."""

    _name = "spp.scoring.value_mapping"
    _description = "Scoring Value Mapping"
    _order = "sequence, id"

    indicator_id = fields.Many2one(
        comodel_name="spp.scoring.indicator",
        string="Indicator",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    # For exact value mapping
    input_value = fields.Char(
        string="Input Value",
        help="Exact value to match (for mapped type)",
    )

    # For range mapping
    range_min = fields.Float(
        string="Range Minimum",
        help="Minimum value (inclusive) for range mapping",
    )
    range_max = fields.Float(
        string="Range Maximum",
        help="Maximum value (inclusive) for range mapping",
    )

    # Output
    output_score = fields.Float(
        string="Output Score",
        required=True,
        help="Score to assign when this mapping matches",
    )
    description = fields.Char(
        string="Description",
        help="Optional description of this mapping",
    )

    @api.constrains("input_value", "range_min", "range_max")
    def _check_mapping_type(self):
        for record in self:
            indicator = record.indicator_id
            if indicator.calculation_type == "mapped":
                # Allow empty string as valid input_value, only reject None/False
                if record.input_value is False or record.input_value is None:
                    raise ValidationError(_("Input value is required for mapped indicator type."))
            elif indicator.calculation_type == "range":
                if record.range_min is None or record.range_max is None:
                    raise ValidationError(_("Range min and max are required for range indicator type."))
                if record.range_min > record.range_max:
                    raise ValidationError(_("Range minimum must be less than or equal to maximum."))

    def name_get(self):
        result = []
        for record in self:
            if record.input_value:
                name = f"{record.input_value} → {record.output_score}"
            else:
                name = f"[{record.range_min}, {record.range_max}] → {record.output_score}"
            result.append((record.id, name))
        return result
