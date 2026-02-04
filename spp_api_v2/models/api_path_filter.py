# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""API Path Filter model for configuring filterable fields per endpoint."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Valid operators per filter type
FILTER_TYPE_OPERATORS = {
    "exact": ["eq", "ne"],
    "contains": ["like", "ilike"],
    "range": ["eq", "ne", "gt", "gte", "lt", "lte"],
    "in": ["in"],
    "nin": ["nin"],
    "null": ["null"],
    "boolean": ["eq"],
    "fulltext": ["match"],
}

# Operator to Odoo domain operator mapping
OPERATOR_MAP = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "like",
    "ilike": "ilike",
    "in": "in",
    "nin": "not in",
    "null": "=",  # Special handling for null checks
}


class SppApiPathFilter(models.Model):
    """
    Define filterable fields for API endpoints.

    Each record configures how a specific field can be filtered
    via URL query parameters or JSON body filters.
    """

    _name = "spp.api.path.filter"
    _description = "API Path Filter Configuration"
    _order = "sequence, name"

    sequence = fields.Integer(default=10, help="Display order in filter list")
    path_id = fields.Many2one(
        "spp.api.path",
        string="API Path",
        required=True,
        ondelete="cascade",
        help="API endpoint this filter applies to",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        related="path_id.model_id",
        store=True,
        help="Model this filter operates on",
    )
    model_name = fields.Char(related="model_id.model", string="Model Name")

    # Filter identification
    name = fields.Char(
        required=True,
        help="Unique filter name used in API parameters (e.g., 'age', 'city')",
    )
    field_path = fields.Char(
        required=True,
        help="Odoo field path. Supports dot notation for related fields "
        "(e.g., 'partner_id.phone', 'program_id.name')",
    )

    # Filter type and operators
    filter_type = fields.Selection(
        [
            ("exact", "Exact Match"),
            ("contains", "Contains (Partial Match)"),
            ("range", "Range (Numeric/Date)"),
            ("in", "In List"),
            ("nin", "Not In List"),
            ("null", "Null Check"),
            ("boolean", "Boolean"),
            ("fulltext", "Full-Text Search"),
        ],
        required=True,
        default="exact",
        help="Type of filtering supported for this field",
    )
    allowed_operators = fields.Char(
        help="Comma-separated list of allowed operators. "
        "Leave empty to use defaults for filter type. "
        "Valid: eq, ne, gt, gte, lt, lte, in, nin, like, ilike, null",
    )

    # Documentation
    label = fields.Char(help="Human-readable label for API documentation")
    description = fields.Text(help="Detailed description for API consumers")

    # Validation
    required = fields.Boolean(
        default=False,
        help="Whether this filter must be provided in API requests",
    )
    default_value = fields.Char(
        help="Default value if filter not provided (JSON format). " "Example: '\"active\"' for string, '18' for number",
    )
    max_values = fields.Integer(
        default=100,
        help="Maximum number of values for 'in'/'nin' filters",
    )

    # Performance and security
    is_indexed = fields.Boolean(
        default=False,
        help="Flag indicating the field has a database index. " "Useful for warning about slow queries.",
    )
    requires_scope = fields.Char(
        help="OAuth scope required to use this filter " "(e.g., 'individual:search:advanced')",
    )

    active = fields.Boolean(default=True)

    @api.constrains("path_id", "name")
    def _check_unique_name_per_path(self):
        """Ensure filter name is unique per API path."""
        for record in self:
            if not record.path_id or not record.name:
                continue

            domain = [
                ("path_id", "=", record.path_id.id),
                ("name", "=", record.name),
                ("id", "!=", record.id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    _("Filter name must be unique per API path. " "A filter named '%s' already exists for this path.")
                    % record.name
                )

    @api.constrains("field_path", "model_id")
    def _check_field_path(self):
        """Validate that field_path references valid model fields."""
        for record in self:
            if not record.model_id or not record.field_path:
                continue

            # Parse field path
            parts = record.field_path.split(".")
            model = self.env[record.model_id.model]

            for i, part in enumerate(parts):
                if part not in model._fields:
                    raise ValidationError(
                        f"Invalid field path '{record.field_path}': "
                        f"field '{part}' does not exist on model '{model._name}'"
                    )

                field = model._fields[part]

                # If not the last part, follow the relation
                if i < len(parts) - 1:
                    if not hasattr(field, "comodel_name"):
                        raise ValidationError(
                            f"Invalid field path '{record.field_path}': " f"field '{part}' is not a relational field"
                        )
                    model = self.env[field.comodel_name]

    @api.constrains("allowed_operators", "filter_type")
    def _check_allowed_operators(self):
        """Validate that allowed_operators are valid for the filter_type."""
        for record in self:
            if not record.allowed_operators:
                continue

            valid_ops = FILTER_TYPE_OPERATORS.get(record.filter_type, [])
            specified_ops = [op.strip() for op in record.allowed_operators.split(",")]

            for op in specified_ops:
                if op not in valid_ops:
                    raise ValidationError(
                        f"Operator '{op}' is not valid for filter type '{record.filter_type}'. "
                        f"Valid operators: {', '.join(valid_ops)}"
                    )

    def get_operators(self):
        """
        Get the list of allowed operators for this filter.

        Returns:
            List of operator strings
        """
        self.ensure_one()
        if self.allowed_operators:
            return [op.strip() for op in self.allowed_operators.split(",")]
        return FILTER_TYPE_OPERATORS.get(self.filter_type, ["eq"])

    def get_default_operator(self):
        """
        Get the default operator for this filter type.

        Returns:
            Default operator string
        """
        self.ensure_one()
        operators = self.get_operators()
        return operators[0] if operators else "eq"

    def validate_value(self, value, operator):
        """
        Validate a filter value against this filter's configuration.

        Args:
            value: The filter value to validate
            operator: The operator being used

        Returns:
            Tuple of (is_valid, error_message)
        """
        self.ensure_one()

        # Check operator is allowed
        allowed = self.get_operators()
        if operator not in allowed:
            return (
                False,
                f"Operator '{operator}' not allowed. Valid: {', '.join(allowed)}",
            )

        # Check max values for in/nin
        if operator in ("in", "nin"):
            if isinstance(value, str):
                values = value.split(",")
            elif isinstance(value, list | tuple):
                values = value
            else:
                values = [value]

            if len(values) > self.max_values:
                return (
                    False,
                    f"Too many values ({len(values)}). Maximum: {self.max_values}",
                )

        return True, None

    def to_domain(self, value, operator=None):
        """
        Convert filter value and operator to Odoo domain.

        Args:
            value: The filter value
            operator: Optional operator override

        Returns:
            List of domain tuples
        """
        self.ensure_one()
        operator = operator or self.get_default_operator()

        # Validate first
        is_valid, error = self.validate_value(value, operator)
        if not is_valid:
            raise ValidationError(error)

        # Handle special cases
        if operator == "null":
            # null=true means field is null, null=false means field is not null
            is_null = str(value).lower() in ("true", "1", "yes")
            return [(self.field_path, "=" if is_null else "!=", False)]

        if operator in ("in", "nin"):
            # Parse comma-separated values
            if isinstance(value, str):
                values = [v.strip() for v in value.split(",")]
            elif isinstance(value, list | tuple):
                values = list(value)
            else:
                values = [value]

            # Type conversion based on field
            values = self._convert_values(values)
            odoo_op = OPERATOR_MAP.get(operator, "in")
            return [(self.field_path, odoo_op, values)]

        if self.filter_type == "boolean":
            bool_value = str(value).lower() in ("true", "1", "yes")
            return [(self.field_path, "=", bool_value)]

        # Standard operators
        odoo_op = OPERATOR_MAP.get(operator, "=")
        converted_value = self._convert_value(value)
        return [(self.field_path, odoo_op, converted_value)]

    def _convert_value(self, value):
        """Convert a single value based on target field type."""
        if not self.model_id or not self.field_path:
            return value

        # Get target field type
        parts = self.field_path.split(".")
        model = self.env[self.model_id.model]

        for i, part in enumerate(parts):
            if part not in model._fields:
                return value
            field = model._fields[part]
            if i < len(parts) - 1:
                model = self.env[field.comodel_name]

        # Convert based on field type
        field_type = field.type

        if field_type == "integer":
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        elif field_type == "float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        elif field_type == "boolean":
            return str(value).lower() in ("true", "1", "yes")
        elif field_type == "date":
            # Return as string, Odoo will handle conversion
            return str(value)
        elif field_type == "datetime":
            return str(value)

        return value

    def _convert_values(self, values):
        """Convert a list of values based on target field type."""
        return [self._convert_value(v) for v in values]

    def to_metadata(self):
        """
        Convert this filter to metadata dictionary for API response.

        Returns:
            Dictionary with filter metadata
        """
        self.ensure_one()
        return {
            "name": self.name,
            "field_path": self.field_path,
            "filter_type": self.filter_type,
            "label": self.label or self.name,
            "description": self.description or "",
            "allowed_operators": self.get_operators(),
            "required": self.required,
            "is_indexed": self.is_indexed,
            "max_values": self.max_values if self.filter_type in ("in", "nin") else None,
        }
