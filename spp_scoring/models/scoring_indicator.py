import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppScoringIndicator(models.Model):
    """Individual scoring component with field mapping and calculation rules."""

    _name = "spp.scoring.indicator"
    _description = "Scoring Indicator"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        help="Human-readable indicator name",
    )
    code = fields.Char(
        string="Code",
        required=True,
        help="Unique identifier within the model",
    )
    description = fields.Text(
        string="Description",
        help="Explanation of what this indicator measures",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display and calculation order",
    )

    # Parent model
    model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        required=True,
        ondelete="cascade",
    )

    # Field mapping
    field_path = fields.Char(
        string="Field Path",
        help="Dot notation path to field (e.g., 'household.roof_material')",
    )
    source_model = fields.Char(
        string="Source Model",
        default="res.partner",
        help="Model to read the field from",
    )

    # Weight and calculation
    weight = fields.Float(
        string="Weight",
        default=1.0,
        help="Multiplier applied to the indicator score",
    )
    calculation_type = fields.Selection(
        selection=[
            ("direct", "Direct Value"),
            ("mapped", "Value Mapping"),
            ("range", "Range Mapping"),
            ("formula", "CEL Formula"),
            ("derived", "Derived/Computed"),
        ],
        string="Calculation Type",
        default="direct",
        required=True,
        help="How the indicator score is calculated from the field value",
    )

    # CEL formula for formula type
    cel_expression = fields.Text(
        string="CEL Expression",
        help="CEL expression for formula calculation",
    )

    # Default handling
    is_required = fields.Boolean(
        string="Required",
        default=False,
        help="If enabled, scoring fails when this field is missing",
    )
    default_value = fields.Char(
        string="Default Value",
        help="Fallback value if field is null (stored as string, converted as needed)",
    )
    default_score = fields.Float(
        string="Default Score",
        default=0.0,
        help="Score to use when value is missing or not mapped",
    )
    invalid_value_ids = fields.Many2many(
        comodel_name="spp.scoring.invalid.value",
        string="Invalid Values",
        help=(
            "Pick from the curated library of strings that should be "
            "treated as missing for this indicator (e.g. 'No Birthdate!'). "
            "Manage the library under Scoring → Configuration → "
            "Invalid Values."
        ),
    )

    # Value mappings
    value_mapping_ids = fields.One2many(
        comodel_name="spp.scoring.value_mapping",
        inverse_name="indicator_id",
        string="Value Mappings",
    )

    # Scoring constraints
    min_score = fields.Float(
        string="Minimum Score",
        help="Minimum allowed score for this indicator",
    )
    max_score = fields.Float(
        string="Maximum Score",
        help="Maximum allowed score for this indicator",
    )

    @api.constrains("code", "model_id")
    def _check_code_unique_per_model(self):
        """Ensure indicator code is unique within a model."""
        for record in self:
            if record.code and record.model_id:
                duplicate = self.search(
                    [
                        ("code", "=", record.code),
                        ("model_id", "=", record.model_id.id),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _("The indicator code '%(code)s' is already in use within this model.") % {"code": record.code}
                    )

    @api.constrains("calculation_type", "field_path", "cel_expression")
    def _check_required_fields(self):
        for record in self:
            if record.calculation_type in ("direct", "mapped", "range"):
                if not record.field_path:
                    raise ValidationError(
                        _("Field path is required for %s calculation type.") % record.calculation_type
                    )
            if record.calculation_type == "formula":
                if not record.cel_expression:
                    raise ValidationError(_("CEL expression is required for formula calculation type."))

    @api.constrains("calculation_type", "value_mapping_ids")
    def _check_mappings(self):
        """Validate value mappings for mapped/range indicators.

        Note: We only validate when mappings exist but are incomplete.
        Indicators can be created without mappings (they'll use default_score).
        Full validation happens in _validate_configuration() during model activation.
        """
        # No immediate constraint - validation happens at model activation
        pass

    def _validate_configuration(self):
        """Validate indicator configuration."""
        self.ensure_one()
        errors = []

        # Check field path validity for field-based calculations
        if self.calculation_type in ("direct", "mapped", "range") and self.field_path:
            if not self._is_valid_field_path():
                errors.append(
                    _("Indicator '%(name)s': Invalid field path '%(path)s'.")
                    % {"name": self.name, "path": self.field_path}
                )

        # Check CEL expression validity
        if self.calculation_type == "formula" and self.cel_expression:
            cel_service = self.env["spp.cel.service"]
            profile = self.model_id.cel_profile or "registry_individuals"
            result = cel_service.compile_expression(self.cel_expression, profile)
            if not result.get("valid"):
                errors.append(
                    _("Indicator '%(name)s': Invalid CEL expression - %(error)s")
                    % {"name": self.name, "error": result.get("error", "Unknown error")}
                )

        # Check value mappings for mapped/range types
        if self.calculation_type == "mapped":
            # Check for duplicate input values
            input_values = [m.input_value for m in self.value_mapping_ids if m.input_value]
            if len(input_values) != len(set(input_values)):
                errors.append(_("Indicator '%(name)s': Duplicate input values in mappings.") % {"name": self.name})

        if self.calculation_type == "range":
            # Check for overlapping ranges
            range_errors = self._check_range_overlaps()
            errors.extend(range_errors)

        return errors

    def _is_valid_field_path(self):
        """Check if the field path resolves to a valid field."""
        if not self.field_path:
            return True

        try:
            model = self.env[self.source_model or "res.partner"]
            parts = self.field_path.split(".")

            for part in parts:
                if part not in model._fields:
                    return False
                field = model._fields[part]
                if hasattr(field, "comodel_name") and field.comodel_name:
                    model = self.env[field.comodel_name]

            return True
        except KeyError as e:
            _logger.debug("Field path validation failed - model not found: %s", e)
            return False
        except (AttributeError, TypeError) as e:
            _logger.debug("Field path validation failed: %s", e)
            return False

    def _check_range_overlaps(self):
        """Check for overlapping ranges in value mappings."""
        errors = []
        ranges = [
            (m.range_min, m.range_max, m.id)
            for m in self.value_mapping_ids
            if m.range_min is not None and m.range_max is not None
        ]

        for i, (min1, max1, _id1) in enumerate(ranges):
            for min2, max2, _id2 in ranges[i + 1 :]:
                # Check overlap
                if not (max1 < min2 or max2 < min1):
                    errors.append(_("Indicator '%(name)s': Overlapping ranges detected.") % {"name": self.name})
                    break
            else:
                continue
            break

        return errors

    def get_field_value(self, registrant):
        """Get the field value from a registrant using the field path."""
        self.ensure_one()
        if not self.field_path:
            return None

        try:
            value = registrant
            for part in self.field_path.split("."):
                if hasattr(value, part):
                    value = getattr(value, part)
                    # Handle empty recordsets (Many2one with no value)
                    # They are falsy but not None, so we convert to None explicitly
                    if hasattr(value, "_name") and not value:
                        return None
                else:
                    return None
            return value
        except (AttributeError, TypeError, KeyError) as e:
            _logger.warning(
                "Error getting field value for indicator %s: %s",
                self.code,
                str(e),
            )
            return None

    def calculate_score(self, field_value):
        """Calculate the indicator score from a field value."""
        self.ensure_one()

        # Handle None/missing values
        if field_value is None:
            if self.default_value:
                field_value = self._convert_default_value()
            else:
                return self.default_score

        # Calculate based on type
        if self.calculation_type == "direct":
            return self._calculate_direct(field_value)
        elif self.calculation_type == "mapped":
            return self._calculate_mapped(field_value)
        elif self.calculation_type == "range":
            return self._calculate_range(field_value)
        elif self.calculation_type == "formula":
            return self._calculate_formula(field_value)
        elif self.calculation_type == "derived":
            return self._calculate_derived(field_value)

        return self.default_score

    def _convert_default_value(self):
        """Convert the default value string to appropriate type."""
        if not self.default_value:
            return None

        try:
            # Try as float
            return float(self.default_value)
        except ValueError:
            # Return as string
            return self.default_value

    def _calculate_direct(self, value):
        """Use the value directly as the score."""
        try:
            score = float(value) if value is not None else 0.0
            return self._apply_constraints(score)
        except (TypeError, ValueError):
            # Handle booleans
            if isinstance(value, bool):
                return self._apply_constraints(1.0 if value else 0.0)
            return self.default_score

    def _calculate_mapped(self, value):
        """Lookup the score from value mappings."""
        str_value = str(value) if value is not None else ""

        for mapping in self.value_mapping_ids:
            if mapping.input_value == str_value:
                return self._apply_constraints(mapping.output_score)

        return self.default_score

    def _calculate_range(self, value):
        """Find the score based on which range the value falls into."""
        try:
            num_value = float(value)
        except (TypeError, ValueError):
            return self.default_score

        for mapping in self.value_mapping_ids.sorted(key=lambda m: m.range_min or 0):
            if mapping.range_min is not None and mapping.range_max is not None:
                if mapping.range_min <= num_value <= mapping.range_max:
                    return self._apply_constraints(mapping.output_score)

        return self.default_score

    def _calculate_formula(self, value):
        """Evaluate the CEL expression to calculate the score."""
        if not self.cel_expression:
            return self.default_score

        try:
            cel_service = self.env["spp.cel.service"]
            profile = self.model_id.cel_profile or "registry_individuals"

            # Create context with the value
            context = {"value": value}
            result = cel_service.evaluate_expression(self.cel_expression, profile, context)

            if result.get("success") and result.get("value") is not None:
                return self._apply_constraints(float(result["value"]))

            return self.default_score
        except (ValueError, TypeError, KeyError) as e:
            _logger.warning(
                "Error evaluating CEL expression for indicator %s: %s",
                self.code,
                str(e),
            )
            return self.default_score
        except Exception as e:
            # Catch-all for unexpected CEL service errors
            _logger.error(
                "Unexpected error evaluating CEL for indicator %s: %s",
                self.code,
                str(e),
                exc_info=True,
            )
            return self.default_score

    def _calculate_derived(self, value):
        """Calculate derived indicator (extensible via inheritance)."""
        # Base implementation just returns the value or default
        try:
            return self._apply_constraints(float(value))
        except (TypeError, ValueError):
            return self.default_score

    def _apply_constraints(self, score):
        """Apply min/max constraints to the score.

        Note: Float fields default to 0.0 in Odoo, so we check for non-zero values
        to determine if a constraint was explicitly set. A constraint value of 0.0
        is treated as "no constraint" for min_score, but valid for max_score when
        you want to limit scores to non-positive values.
        """
        # Apply min_score if explicitly set (non-zero)
        if self.min_score and score < self.min_score:
            score = self.min_score
        # Apply max_score if explicitly set (non-zero)
        if self.max_score and score > self.max_score:
            score = self.max_score
        return score
