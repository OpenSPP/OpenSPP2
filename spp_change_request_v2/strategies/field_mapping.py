import logging
from datetime import date, datetime

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class SPPCRStrategyFieldMapping(models.AbstractModel):
    """Apply strategy: copy fields from detail to registrant."""

    _name = "spp.cr.strategy.field_mapping"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply Strategy: Field Mapping"

    def apply(self, change_request):
        """Apply field mappings from detail to registrant."""
        registrant = change_request.registrant_id
        detail = change_request.get_detail()
        cr_type = change_request.request_type_id

        if not detail:
            raise UserError(_("No detail record found."))

        values = {}
        for mapping in cr_type.apply_mapping_ids:
            source_value = getattr(detail, mapping.source_field, None)
            current_value = getattr(registrant, mapping.target_field, None)

            # Handle relational fields - get ID
            if hasattr(source_value, "id"):
                source_value = source_value.id
            if hasattr(current_value, "id"):
                current_value = current_value.id

            # Apply transform if configured
            if mapping.transform == "expression" and mapping.transform_expression:
                source_value = self._eval_expression(
                    mapping.transform_expression,
                    source_value,
                    detail,
                    registrant,
                )

            # Skip if value hasn't changed
            if source_value == current_value:
                continue

            # Skip empty values (None, empty strings, empty collections)
            # COMMENTED OUT: Users may want to intentionally clear fields
            # if not self._is_value_empty(source_value, registrant, mapping.target_field):
            #     values[mapping.target_field] = source_value

            # Apply the value (including empty values for intentional clearing)
            values[mapping.target_field] = source_value

        if values:
            _logger.info(
                "Applying field mapping for CR %s: %s",
                change_request.name,
                list(values.keys()),
            )
            registrant.write(values)

            # Only regenerate name if name-related fields were updated
            name_related_fields = {"family_name", "given_name", "addl_name"}
            if name_related_fields & set(values.keys()):
                registrant.name_change()

        return True

    def _eval_expression(self, expr, value, detail, registrant):
        """Safely evaluate transform expression."""
        try:
            return safe_eval(  # nosemgrep: odoo-unsafe-safe-eval
                # Admin-defined field mapping expressions with restricted context (no env);
                # reviewed as part of CR strategy engine.
                expr,
                {
                    "value": value,
                    "detail": detail,
                    "registrant": registrant,
                    # env removed for security
                    "datetime": datetime,
                    "date": date,
                },
                mode="eval",
                nocopy=True,
            )
        except Exception as e:
            _logger.warning("Expression eval failed: %s", e)
            return value

    def _is_value_empty(self, value, record=None, field_name=None):
        """Check if a value should be considered empty and skipped.

        Returns True if the value is:
        - None
        - False (for non-Boolean fields; Odoo uses False to represent empty fields)
        - Empty string (after stripping whitespace)
        - Empty collection (list, tuple, set)
        - Numeric 0 is considered a valid value and returns False

        Note: In Odoo's ORM, False is commonly used to represent "no value"
        for Char, Text, Many2one, and other field types. However, for Boolean
        fields, False is a legitimate value.

        Args:
            value: The value to check
            record: Optional recordset to determine field type
            field_name: Optional field name to check field type

        Returns:
            bool: True if value should be skipped, False otherwise
        """
        # None is always considered empty
        if value is None:
            return True

        # Check if False is a valid value for Boolean fields
        if value is False:
            # If we have field information, check if it's a Boolean field
            if record and field_name and field_name in record._fields:
                field = record._fields[field_name]
                # For Boolean fields, False is a valid value
                if field.type == "boolean":
                    return False
            # For non-Boolean fields, False means empty
            return True

        # Numeric 0 is a legitimate value, not empty
        if value == 0 and isinstance(value, int | float):
            return False

        # Empty string (including whitespace-only strings)
        if isinstance(value, str) and not value.strip():
            return True

        # Empty collections (list, tuple, set)
        if isinstance(value, list | tuple | set) and len(value) == 0:
            return True

        return False

    def preview(self, change_request):
        """Preview what changes will be applied."""
        registrant = change_request.registrant_id
        detail = change_request.get_detail()
        cr_type = change_request.request_type_id

        if not detail:
            return {}

        changes = {}
        for mapping in cr_type.apply_mapping_ids:
            source_value = getattr(detail, mapping.source_field, None)
            current_value = getattr(registrant, mapping.target_field, None)

            # Skip empty values (same logic as apply)
            # COMMENTED OUT: Users may want to intentionally clear fields
            # if self._is_value_empty(source_value, registrant, mapping.target_field):
            #     continue

            # Normalize for comparison
            if hasattr(source_value, "id"):
                source_value = source_value.id
            if hasattr(current_value, "id"):
                current_value = current_value.id

            # Only show fields that actually changed
            if source_value != current_value:
                changes[mapping.target_field] = {
                    "old": current_value,
                    "new": source_value,
                }

        return changes
