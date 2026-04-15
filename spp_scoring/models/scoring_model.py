import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppScoringModel(models.Model):
    """Defines a scoring methodology with indicators, weights, and thresholds."""

    _name = "spp.scoring.model"
    _description = "Scoring Model"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="Human-readable name (e.g., '2024 PMT Model - Urban')",
    )
    code = fields.Char(
        string="Code",
        required=True,
        tracking=True,
        help="Unique identifier (e.g., 'PMT_2024_URBAN')",
    )
    version = fields.Char(
        string="Version",
        default="1.0",
        tracking=True,
        help="Version number (e.g., '1.0', '2.1')",
    )
    description = fields.Text(
        string="Description",
        help="Detailed description of this scoring model",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order",
    )

    # Classification
    category = fields.Selection(
        selection=[
            ("poverty", "Poverty Assessment"),
            ("vulnerability", "Vulnerability Assessment"),
            ("eligibility", "Eligibility Scoring"),
            ("triage", "Triage/Prioritization"),
            ("custom", "Custom"),
        ],
        string="Category",
        default="custom",
        required=True,
        tracking=True,
        help="Purpose classification for this scoring model",
    )

    # Calculation Method
    calculation_method = fields.Selection(
        selection=[
            ("weighted_sum", "Weighted Sum"),
            ("cel_formula", "CEL Formula"),
            ("lookup_table", "Lookup Table"),
            ("external", "External Service"),
            ("custom", "Custom Plugin"),
        ],
        string="Calculation Method",
        default="weighted_sum",
        required=True,
        tracking=True,
        help="How the total score is calculated from indicators",
    )
    cel_expression = fields.Text(
        string="CEL Expression",
        help="CEL expression for formula-based calculation",
    )
    cel_profile = fields.Char(
        string="CEL Profile",
        default="registry_individuals",
        help="CEL profile to use for expression evaluation",
    )

    # Validity
    is_active = fields.Boolean(
        string="Active",
        default=False,
        tracking=True,
        help="Only active models can be used for scoring",
    )
    effective_date = fields.Date(
        string="Effective Date",
        help="Date from which this model becomes valid",
    )
    end_date = fields.Date(
        string="End Date",
        help="Date after which this model is no longer valid",
    )

    # Behavior settings
    is_strict_mode = fields.Boolean(
        string="Strict Mode",
        default=False,
        help="If enabled, scoring fails when required indicators are missing",
    )
    expected_total_weight = fields.Float(
        string="Expected Total Weight",
        default=1.0,
        help="Expected sum of all indicator weights (for validation)",
    )

    # Related records
    indicator_ids = fields.One2many(
        comodel_name="spp.scoring.indicator",
        inverse_name="model_id",
        string="Indicators",
        copy=True,
    )
    threshold_ids = fields.One2many(
        comodel_name="spp.scoring.threshold",
        inverse_name="model_id",
        string="Thresholds",
        copy=True,
    )
    result_ids = fields.One2many(
        comodel_name="spp.scoring.result",
        inverse_name="model_id",
        string="Scoring Results",
    )

    # Computed
    indicator_count = fields.Integer(
        string="Indicator Count",
        compute="_compute_indicator_count",
    )
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_result_count",
    )
    total_weight = fields.Float(
        string="Total Weight",
        compute="_compute_total_weight",
        help="Sum of all indicator weights",
    )

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure scoring model code is unique."""
        for record in self:
            if record.code:
                duplicate = self.search(
                    [
                        ("code", "=", record.code),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _("The code '%(code)s' is already in use by another scoring model.") % {"code": record.code}
                    )

    @api.depends("indicator_ids")
    def _compute_indicator_count(self):
        for record in self:
            record.indicator_count = len(record.indicator_ids)

    @api.depends("result_ids")
    def _compute_result_count(self):
        Result = self.env["spp.scoring.result"]
        for record in self:
            record.result_count = Result.search_count([("model_id", "=", record.id)])

    @api.depends("indicator_ids.weight")
    def _compute_total_weight(self):
        for record in self:
            record.total_weight = sum(record.indicator_ids.mapped("weight"))

    @api.constrains("effective_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.effective_date and record.end_date:
                if record.effective_date > record.end_date:
                    raise ValidationError(_("Effective date must be before end date."))

    @api.constrains("cel_expression", "calculation_method")
    def _check_cel_expression(self):
        for record in self:
            if record.calculation_method == "cel_formula" and not record.cel_expression:
                raise ValidationError(_("CEL expression is required for CEL formula calculation method."))

    def is_active_on_date(self, check_date):
        """Check if this model is active on the given date."""
        self.ensure_one()
        if not self.is_active:
            return False
        if self.effective_date and check_date < self.effective_date:
            return False
        if self.end_date and check_date > self.end_date:
            return False
        return True

    def action_activate(self):
        """Activate the scoring model after validation."""
        for record in self:
            errors = record._validate_configuration()
            if errors:
                raise ValidationError(
                    _("Cannot activate model '%(name)s'. Validation errors:\n%(errors)s")
                    % {"name": record.name, "errors": "\n".join(f"• {e}" for e in errors)}
                )
            record.is_active = True
        return True

    def action_deactivate(self):
        """Deactivate the scoring model."""
        self.write({"is_active": False})
        return True

    def _validate_configuration(self):
        """Validate model configuration before activation."""
        self.ensure_one()
        errors = []

        # Check indicators exist
        if not self.indicator_ids:
            errors.append(_("No indicators defined. Add at least one indicator in the Indicators tab."))

        # Check thresholds exist
        if not self.threshold_ids:
            errors.append(_("No thresholds defined. Add at least one threshold in the Thresholds tab."))

        # Check weights sum correctly (if expected)
        if self.expected_total_weight > 0:
            weight_diff = abs(self.total_weight - self.expected_total_weight)
            if weight_diff > 0.01:
                errors.append(
                    _("Indicator weights sum to %(actual)s, expected %(expected)s.")
                    % {
                        "actual": self.total_weight,
                        "expected": self.expected_total_weight,
                    }
                )

        # Check CEL expression validity
        if self.calculation_method == "cel_formula" and self.cel_expression:
            cel_service = self.env["spp.cel.service"]
            result = cel_service.compile_expression(self.cel_expression, self.cel_profile or "registry_individuals")
            if not result.get("valid"):
                errors.append(_("Invalid CEL expression: %s") % result.get("error", "Unknown error"))

        # Check threshold coverage
        threshold_errors = self._validate_thresholds()
        errors.extend(threshold_errors)

        # Validate each indicator
        for indicator in self.indicator_ids:
            indicator_errors = indicator._validate_configuration()
            errors.extend(indicator_errors)

        return errors

    def _validate_thresholds(self):
        """Check that thresholds cover the expected score range without gaps or overlaps."""
        errors = []
        if not self.threshold_ids:
            return errors

        sorted_thresholds = self.threshold_ids.sorted(key=lambda t: t.min_score)

        # Check all consecutive threshold boundaries for gaps and overlaps
        for i, threshold in enumerate(sorted_thresholds[:-1]):
            next_threshold = sorted_thresholds[i + 1]
            gap = next_threshold.min_score - threshold.max_score

            if gap > 0.01:
                errors.append(
                    _("Gap detected between thresholds '%(current)s' (max %(max)s) and '%(next)s' (min %(min)s).")
                    % {
                        "current": threshold.name,
                        "max": threshold.max_score,
                        "next": next_threshold.name,
                        "min": next_threshold.min_score,
                    }
                )
            elif gap < -0.01:
                errors.append(
                    _("Overlap detected between thresholds '%(current)s' (max %(max)s) and '%(next)s' (min %(min)s).")
                    % {
                        "current": threshold.name,
                        "max": threshold.max_score,
                        "next": next_threshold.name,
                        "min": next_threshold.min_score,
                    }
                )

        return errors

    def action_view_results(self):
        """Open the list of scoring results for this model."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scoring Results"),
            "res_model": "spp.scoring.result",
            "view_mode": "list,form",
            "domain": [("model_id", "=", self.id)],
            "context": {"default_model_id": self.id},
        }

    def copy(self, default=None):
        """Create a copy with updated code and version."""
        default = default or {}
        if not default.get("code"):
            default["code"] = _("%s (copy)") % self.code
        if not default.get("name"):
            default["name"] = _("%s (copy)") % self.name
        default["is_active"] = False
        return super().copy(default)
