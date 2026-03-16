# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.sql import SQL

_logger = logging.getLogger(__name__)


@dataclass
class SQLColumnResult:
    """Result of compiling a demographic dimension to a SQL expression."""

    expression: SQL
    joins: list[SQL] = dataclass_field(default_factory=list)
    alias_counter: int = 0


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
        if hasattr(value, "_name"):
            # Odoo recordset (Many2one). Empty recordset means the field is unset.
            if not value:
                return self.default_value or "unknown"
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

        First checks value_labels_json for a static mapping. If not found and
        the dimension is field-based pointing to a Many2one, dynamically looks
        up the display_name from the related model.

        :param value: The raw dimension value
        :returns: Display label
        :rtype: str
        """
        self.ensure_one()

        # Check static labels first
        if self.value_labels_json:
            labels = self.value_labels_json
            if isinstance(labels, str):
                try:
                    labels = json.loads(labels)
                except (json.JSONDecodeError, TypeError):
                    labels = {}

            str_value = str(value) if value is not None else "null"
            if str_value in labels:
                return labels[str_value]

        # For field-based dimensions pointing to a Many2one, try dynamic lookup
        if self.dimension_type == "field" and self.field_path:
            label = self._lookup_m2o_label(value)
            if label:
                return label

        return value

    def _lookup_m2o_label(self, raw_value):
        """Look up display_name for a Many2one field-based dimension value.

        When field_path points to a Many2one (e.g. area_id, gender_id), the raw
        value is typically the record's code. This method searches the related
        model by code to return the display_name.

        :param raw_value: The raw dimension value (typically a code string)
        :returns: display_name or None if not found
        """
        # Only handle simple field paths (one segment, no dotted traversal
        # like "gender_id.code" where the user explicitly chose a sub-field)
        if "." in self.field_path:
            return None

        field_name = self.field_path
        partner_fields = self.env["res.partner"]._fields
        if field_name not in partner_fields:
            return None

        field = partner_fields[field_name]
        if field.type != "many2one":
            return None

        comodel = self.env[field.comodel_name]
        # Search by code if the related model has a code field
        if "code" in comodel._fields:
            record = comodel.search([("code", "=", raw_value)], limit=1)
            if record:
                return record.display_name

        return None

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
    # SQL Column Generation
    # -------------------------------------------------------------------------
    def to_sql_column(self, alias="ind", alias_counter=0):
        """Generate a SQL expression for this dimension's value.

        Compiles this dimension to a SQL expression that can be used in a
        SELECT clause. For field-based dimensions, generates column references
        (with JOINs for Many2one). For CEL expression dimensions, delegates to
        the CEL-to-SQL compiler.

        Args:
            alias: SQL alias for the res_partner table (default "ind")
            alias_counter: Counter for generating unique join aliases

        Returns:
            SQLColumnResult | None: SQL expression + joins, or None if
                SQL compilation is not possible (fall back to Python).
        """
        self.ensure_one()
        default = self.default_value or "unknown"

        if self.dimension_type == "field":
            result = self._to_sql_column_field(alias, alias_counter, default)
        elif self.dimension_type == "expression":
            result = self._to_sql_column_expression(alias, alias_counter, default)
        else:
            return None

        if result is None:
            return None

        # Wrap with applies_to filter: return default for non-matching registrants
        if self.applies_to == "individuals":
            result = SQLColumnResult(
                expression=SQL(
                    "CASE WHEN %s.%s = FALSE THEN %s ELSE %s END",
                    SQL.identifier(alias),
                    SQL.identifier("is_group"),
                    result.expression,
                    SQL("%s", default),
                ),
                joins=result.joins,
                alias_counter=result.alias_counter,
            )
        elif self.applies_to == "groups":
            result = SQLColumnResult(
                expression=SQL(
                    "CASE WHEN %s.%s = TRUE THEN %s ELSE %s END",
                    SQL.identifier(alias),
                    SQL.identifier("is_group"),
                    result.expression,
                    SQL("%s", default),
                ),
                joins=result.joins,
                alias_counter=result.alias_counter,
            )

        return result

    def _to_sql_column_field(self, alias, alias_counter, default):
        """Generate SQL for a field-based dimension."""
        if not self.field_path:
            return None

        parts = self.field_path.split(".")
        partner_fields = self.env["res.partner"]._fields

        if len(parts) == 1:
            # Simple field (e.g., is_group, area_id)
            field_name = parts[0]
            if field_name not in partner_fields:
                return None

            field_def = partner_fields[field_name]
            if field_def.type == "many2one":
                # Many2one direct: use code from related model if available
                return self._to_sql_column_m2o_direct(alias, alias_counter, field_name, field_def, default)
            else:
                # Scalar field: CAST to text
                col = SQL("%s.%s", SQL.identifier(alias), SQL.identifier(field_name))
                expr = SQL("COALESCE(CAST(%s AS TEXT), %s)", col, default)
                return SQLColumnResult(expression=expr, alias_counter=alias_counter)

        elif len(parts) == 2:
            # Dotted path (e.g., gender_id.code)
            field_name, sub_field = parts
            if field_name not in partner_fields:
                return None

            field_def = partner_fields[field_name]
            if field_def.type != "many2one":
                return None

            return self._to_sql_column_m2o_sub(alias, alias_counter, field_name, field_def, sub_field, default)

        # Deeper paths not supported in SQL
        return None

    def _to_sql_column_m2o_direct(self, alias, alias_counter, field_name, field_def, default):
        """Generate SQL for a direct Many2one field (e.g., gender_id, area_id).

        JOINs to the comodel and uses code if available, otherwise id as text.
        """
        comodel_name = field_def.comodel_name
        comodel = self.env[comodel_name]
        join_alias = f"_dim{alias_counter}"
        comodel_table = comodel._table

        fk_col = SQL("%s.%s", SQL.identifier(alias), SQL.identifier(field_name))
        join_id = SQL("%s.id", SQL.identifier(join_alias))
        join_sql = SQL(
            "LEFT JOIN %s %s ON %s = %s",
            SQL.identifier(comodel_table),
            SQL.identifier(join_alias),
            join_id,
            fk_col,
        )

        if "code" in comodel._fields:
            code_col = SQL("%s.%s", SQL.identifier(join_alias), SQL.identifier("code"))
            expr = SQL("COALESCE(CAST(%s AS TEXT), %s)", code_col, default)
        else:
            id_col = SQL("%s.id", SQL.identifier(join_alias))
            expr = SQL("COALESCE(CAST(%s AS TEXT), %s)", id_col, default)

        return SQLColumnResult(expression=expr, joins=[join_sql], alias_counter=alias_counter + 1)

    def _to_sql_column_m2o_sub(self, alias, alias_counter, field_name, field_def, sub_field, default):
        """Generate SQL for a Many2one dotted path (e.g., gender_id.code)."""
        comodel_name = field_def.comodel_name
        comodel = self.env[comodel_name]
        join_alias = f"_dim{alias_counter}"
        comodel_table = comodel._table

        if sub_field not in comodel._fields:
            return None

        fk_col = SQL("%s.%s", SQL.identifier(alias), SQL.identifier(field_name))
        join_id = SQL("%s.id", SQL.identifier(join_alias))
        join_sql = SQL(
            "LEFT JOIN %s %s ON %s = %s",
            SQL.identifier(comodel_table),
            SQL.identifier(join_alias),
            join_id,
            fk_col,
        )

        sub_col = SQL("%s.%s", SQL.identifier(join_alias), SQL.identifier(sub_field))
        expr = SQL("COALESCE(CAST(%s AS TEXT), %s)", sub_col, default)

        return SQLColumnResult(expression=expr, joins=[join_sql], alias_counter=alias_counter + 1)

    def _to_sql_column_expression(self, alias, alias_counter, default):
        """Generate SQL for a CEL expression-based dimension."""
        if not self.cel_expression:
            return None

        try:
            translator = self.env["spp.cel.translator"]
        except KeyError:
            return None

        sql_expr = translator.to_sql_case(self.cel_expression, "res.partner", alias)
        if sql_expr is None:
            return None

        expr = SQL("COALESCE(CAST(%s AS TEXT), %s)", sql_expr, default)
        return SQLColumnResult(expression=expr, alias_counter=alias_counter)

    # -------------------------------------------------------------------------
    # Cache Invalidation
    # -------------------------------------------------------------------------
    def write(self, vals):
        """Clear cache when dimension configuration changes."""
        result = super().write(vals)
        cache_service = self.env["spp.metrics.dimension.cache"]
        for record in self:
            cache_service.clear_dimension_cache(record.id)
        return result

    def unlink(self):
        """Clear cache when dimension is deleted."""
        cache_service = self.env["spp.metrics.dimension.cache"]
        for record in self:
            cache_service.clear_dimension_cache(record.id)
        return super().unlink()
