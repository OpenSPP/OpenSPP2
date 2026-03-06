# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DemographicDimension(models.Model):
    """
    Configurable demographic dimensions for group_by breakdowns.

    Examples:
    - gender: Field-based lookup on gender_id.code
    - disability_status: CEL expression r.disability_id != null
    - age_group: CEL expression age_bucket(r.birthdate)
    - area: Field-based lookup on area_id
    """

    _name = "spp.demographic.dimension"
    _description = "Demographic Dimension"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        index=True,
        help="Technical name for this dimension (e.g., 'gender', 'disability_status').",
    )
    label = fields.Char(
        string="Label",
        required=True,
        translate=True,
        help="Human-readable label (e.g., 'Gender', 'Disability Status').",
    )
    description = fields.Text(
        help="Optional description of what this dimension represents.",
    )
    sequence = fields.Integer(
        default=10,
        help="Display order in UI.",
    )
    active = fields.Boolean(
        default=True,
        index=True,
    )

    dimension_type = fields.Selection(
        selection=[
            ("field", "Model Field"),
            ("expression", "CEL Expression"),
        ],
        required=True,
        default="field",
        help="How to evaluate this dimension for a registrant.",
    )

    # -------------------------------------------------------------------------
    # Field-based dimensions
    # -------------------------------------------------------------------------
    field_path = fields.Char(
        string="Field Path",
        help=(
            "Dot-notation path to the field value (e.g., 'gender_id.code', 'area_id.id'). "
            "For direct fields, just use the field name (e.g., 'age')."
        ),
    )

    # -------------------------------------------------------------------------
    # CEL-based dimensions
    # -------------------------------------------------------------------------
    cel_expression = fields.Text(
        string="CEL Expression",
        help=(
            "CEL expression that returns a category value for each registrant. "
            "Use 'r' for the registrant record. "
            "Example: age_bucket(r.birthdate) or r.disability_id != null ? 'pwd' : 'non_pwd'"
        ),
    )

    # -------------------------------------------------------------------------
    # Value configuration
    # -------------------------------------------------------------------------
    value_labels_json = fields.Json(
        string="Value Labels",
        help=('JSON mapping of raw values to display labels. Example: {"M": "Male", "F": "Female", "O": "Other"}'),
    )
    default_value = fields.Char(
        string="Default Value",
        default="unknown",
        help="Value to use when the dimension cannot be evaluated (null/missing).",
    )

    # -------------------------------------------------------------------------
    # Applicability
    # -------------------------------------------------------------------------
    applies_to = fields.Selection(
        selection=[
            ("all", "All Registrants"),
            ("individuals", "Individuals Only"),
            ("groups", "Groups Only"),
        ],
        default="all",
        help="Which registrant types this dimension applies to.",
    )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    _name_unique = models.Constraint(
        "unique(name)",
        "Dimension name must be unique.",
    )

    @api.constrains("dimension_type", "field_path")
    def _check_field_path(self):
        """Validate field path is provided for field-based dimensions."""
        for dim in self:
            if dim.dimension_type == "field" and not dim.field_path:
                raise ValidationError(_("Field path is required for field-based dimensions."))

    @api.constrains("dimension_type", "cel_expression")
    def _check_cel_expression(self):
        """Validate CEL expression is provided for expression-based dimensions."""
        for dim in self:
            if dim.dimension_type == "expression" and not dim.cel_expression:
                raise ValidationError(_("CEL expression is required for expression-based dimensions."))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def evaluate_for_record(self, record):
        """
        Evaluate this dimension for a single registrant record.

        :param record: res.partner record
        :returns: The dimension value (string)
        :rtype: str
        """
        self.ensure_one()

        # Check applicability
        if self.applies_to == "individuals" and record.is_group:
            return self.default_value or "n/a"
        if self.applies_to == "groups" and not record.is_group:
            return self.default_value or "n/a"

        try:
            if self.dimension_type == "field":
                return self._evaluate_field(record)
            else:
                return self._evaluate_expression(record)
        except (ValueError, AttributeError, TypeError, KeyError) as e:
            dimension_name = self.name
            record_id = record.id
            _logger.warning("Error evaluating dimension %s for record %s: %s", dimension_name, record_id, e)
            return self.default_value or "error"

    def _evaluate_field(self, record):
        """Evaluate a field-based dimension."""
        value = record
        for part in self.field_path.split("."):
            if value is None:
                break
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                value = None
                break

        if value is None:
            return self.default_value or "unknown"

        # Convert to string key
        if hasattr(value, "id"):
            # Many2one - use code or display_name for meaningful keys
            if hasattr(value, "code") and value.code:
                key = str(value.code)
            else:
                key = value.display_name or str(value.id)
        elif isinstance(value, bool):
            key = str(value).lower()
        else:
            key = str(value) if value else self.default_value

        return key

    def _evaluate_expression(self, record):
        """Evaluate a CEL expression-based dimension."""
        try:
            cel_service = self.env["spp.cel.service"].sudo()  # nosemgrep: odoo-sudo-without-context
        except KeyError:
            dimension_name = self.name
            _logger.warning("CEL service not available for dimension %s", dimension_name)
            return self.default_value or "error"

        context = {"r": record, "me": record}
        result = cel_service.evaluate_expression(self.cel_expression, context)

        if result is None:
            return self.default_value or "unknown"

        # Convert bool to string category
        if isinstance(result, bool):
            return "true" if result else "false"

        return str(result)

    def get_label_for_value(self, value):
        """
        Get the display label for a dimension value.

        :param value: The raw dimension value
        :returns: Display label
        :rtype: str
        """
        self.ensure_one()
        if not self.value_labels_json:
            return value

        # Handle case where value_labels_json is a string (JSON not yet parsed)
        labels = self.value_labels_json
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except (json.JSONDecodeError, TypeError):
                return value

        # Convert value to string for lookup (keys are strings in JSON)
        str_value = str(value) if value is not None else "null"
        if str_value in labels:
            return labels[str_value]
        return value

    @api.model
    def get_by_name(self, name):
        """
        Get a dimension by its technical name.

        :param name: Technical name of the dimension
        :returns: Dimension record or empty recordset
        :rtype: spp.demographic.dimension
        """
        return self.search([("name", "=", name), ("active", "=", True)], limit=1)

    @api.model
    def get_active_dimensions(self, applies_to=None):
        """
        Get all active dimensions, optionally filtered by applicability.

        :param applies_to: Filter by 'individuals', 'groups', or None for all
        :returns: Recordset of dimensions
        :rtype: spp.demographic.dimension
        """
        domain = [("active", "=", True)]
        if applies_to:
            domain.append("|")
            domain.append(("applies_to", "=", "all"))
            domain.append(("applies_to", "=", applies_to))
        return self.search(domain, order="sequence, name")

    # -------------------------------------------------------------------------
    # Cache Invalidation
    # -------------------------------------------------------------------------
    def write(self, vals):
        """Clear cache when dimension configuration changes."""
        result = super().write(vals)
        cache_service = self.env["spp.metric.dimension.cache"]
        for record in self:
            cache_service.clear_dimension_cache(record.id)
        return result

    def unlink(self):
        """Clear cache when dimension is deleted."""
        cache_service = self.env["spp.metric.dimension.cache"]
        for record in self:
            cache_service.clear_dimension_cache(record.id)
        return super().unlink()
