from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SppScoringThreshold(models.Model):
    """Maps score ranges to classifications."""

    _name = "spp.scoring.threshold"
    _description = "Scoring Threshold"
    _order = "sequence, min_score"

    model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Name",
        required=True,
        help="Human-readable threshold name",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    # Score range
    min_score = fields.Float(
        string="Minimum Score",
        required=True,
        help="Minimum score (inclusive) for this classification",
    )
    max_score = fields.Float(
        string="Maximum Score",
        required=True,
        help="Maximum score (inclusive) for this classification",
    )

    # Classification
    classification_code = fields.Char(
        string="Classification Code",
        required=True,
        help="Machine-readable code (e.g., 'EXTREME_POOR')",
    )
    classification_label = fields.Char(
        string="Classification Label",
        required=True,
        help="Human-readable label (e.g., 'Extremely Poor')",
    )

    # Display
    display_color = fields.Selection(
        selection=[
            ("red", "Red"),
            ("orange", "Orange"),
            ("yellow", "Yellow"),
            ("green", "Green"),
            ("blue", "Blue"),
            ("purple", "Purple"),
            ("gray", "Gray"),
        ],
        string="Display Color",
        default="gray",
        help="Color for visual representation",
    )

    # Optional CEL rule for complex threshold logic
    cel_rule = fields.Text(
        string="CEL Rule",
        help="Optional CEL expression for complex threshold logic",
    )

    @api.constrains("classification_code", "model_id")
    def _check_classification_code_unique(self):
        """Ensure classification code is unique within a model."""
        for record in self:
            if record.classification_code and record.model_id:
                duplicate = self.search(
                    [
                        ("classification_code", "=", record.classification_code),
                        ("model_id", "=", record.model_id.id),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Classification code must be unique within a model!"))

    @api.constrains("min_score", "max_score")
    def _check_score_range(self):
        for record in self:
            if record.min_score > record.max_score:
                raise ValidationError(_("Minimum score must be less than or equal to maximum score."))

    def matches_score(self, score):
        """Check if a score falls within this threshold's range."""
        self.ensure_one()
        return self.min_score <= score <= self.max_score

    def get_classification(self):
        """Return the classification dict for this threshold."""
        self.ensure_one()
        return {
            "code": self.classification_code,
            "label": self.classification_label,
            "color": self.display_color,
        }
