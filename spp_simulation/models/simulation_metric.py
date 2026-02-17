import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SimulationMetric(models.Model):
    """Custom evaluation metrics for simulation scenarios.

    Inherits from spp.metric.base for common metric fields
    (name, label, description, unit, decimal_places, category_id, active, sequence).

    Defines simulation-specific computation fields:
    - metric_type (aggregate/coverage/ratio)
    - cel_expression (for aggregate and coverage metrics)
    - aggregation (how to aggregate across groups)
    - numerator/denominator expressions (for ratio metrics)
    """

    _name = "spp.simulation.metric"
    _description = "Simulation Metric"
    _inherit = ["spp.metric.base"]
    _order = "sequence, name"

    # name, label, description, unit, decimal_places, category_id, active, sequence
    # inherited from spp.metric.base

    # ─── Computation ────────────────────────────────────────────────────
    metric_type = fields.Selection(
        selection=[
            ("aggregate", "Aggregate"),
            ("coverage", "Coverage"),
            ("ratio", "Ratio"),
        ],
        string="Metric Type",
        required=True,
        default="aggregate",
        help="Type of simulation metric computation",
    )

    cel_expression = fields.Text(
        string="CEL Expression",
        help="CEL expression for computation (required for aggregate and coverage metrics)",
    )

    aggregation = fields.Selection(
        selection=[
            ("sum", "Sum"),
            ("avg", "Average"),
            ("min", "Minimum"),
            ("max", "Maximum"),
            ("count", "Count"),
        ],
        string="Aggregation",
        default="sum",
        help="How to aggregate across groups",
    )

    numerator_expression = fields.Text(
        string="Numerator Expression",
        help="CEL expression for the numerator of ratio metrics.",
    )
    denominator_expression = fields.Text(
        string="Denominator Expression",
        help="CEL expression for the denominator of ratio metrics.",
    )

    @api.constrains("metric_type", "cel_expression")
    def _check_aggregate_expression(self):
        for record in self:
            if record.metric_type in ("aggregate", "coverage") and not record.cel_expression:
                raise ValidationError(_("CEL expression is required for aggregate and coverage metrics."))

    @api.constrains("metric_type", "numerator_expression", "denominator_expression")
    def _check_ratio_expressions(self):
        for record in self:
            if record.metric_type == "ratio":
                if not record.numerator_expression or not record.denominator_expression:
                    raise ValidationError(
                        _("Both numerator and denominator expressions are required for ratio metrics.")
                    )
