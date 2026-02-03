import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Claim169AttributeMapping(models.Model):
    """
    Configurable mapping from OpenSPP fields to Claim 169 numbered attributes.

    This model allows administrators to define how res.partner fields
    map to MOSIP Claim 169 attribute numbers for credential generation.
    """

    _name = "spp.claim169.attribute.mapping"
    _description = "Claim 169 Attribute Mapping"
    _order = "sequence, claim_number"

    name = fields.Char(string="Mapping Name", required=True, help="Descriptive name for this attribute mapping")

    claim_number = fields.Integer(string="Claim Number", required=True, help="Claim 169 attribute number (1-99)")

    claim_name = fields.Char(string="Claim Name", help="Human-readable claim name (e.g., 'full_name', 'dob')")

    source_field = fields.Char(
        string="Source Field", required=True, help="Field path on res.partner (e.g., 'name', 'birthdate', 'phone')"
    )

    transform_type = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("date_yyyymmdd", "Date YYYYMMDD"),
            ("gender_code", "Gender Code"),
            ("address_combined", "Address Combined"),
            ("cel", "CEL Expression"),
        ],
        string="Transform Type",
        required=True,
        default="direct",
        help="How to transform the source value",
    )

    cel_expression = fields.Text(
        string="CEL Expression", help="CEL expression for complex transformations (when transform_type='cel')"
    )

    is_active = fields.Boolean(
        string="Active", default=True, help="Only active mappings are used in credential generation"
    )

    sequence = fields.Integer(string="Sequence", default=10, help="Order of processing (lower numbers first)")

    @api.constrains("claim_number")
    def _check_claim_number(self):
        """Validate that claim number is in valid range."""
        for record in self:
            if record.claim_number < 1 or record.claim_number > 99:
                raise ValidationError(_("Claim number must be between 1 and 99 (got %s)") % record.claim_number)

    @api.constrains("claim_number", "is_active")
    def _check_unique_active_claim_number(self):
        """Ensure only one active mapping per claim number."""
        for record in self:
            if record.is_active:
                duplicate = self.search(
                    [
                        ("id", "!=", record.id),
                        ("claim_number", "=", record.claim_number),
                        ("is_active", "=", True),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _("Only one active mapping allowed per claim number. " "Claim %s is already mapped by '%s'")
                        % (record.claim_number, duplicate.name)
                    )

    def get_value(self, partner):
        """
        Extract and transform the value from the partner record.

        Args:
            partner: res.partner recordset (single record)

        Returns:
            Transformed value appropriate for the claim type, or None if not available
        """
        self.ensure_one()

        if not partner:
            return None

        # Get the raw value from the source field
        raw_value = self._get_field_value(partner, self.source_field)

        if raw_value is None or raw_value is False:
            return None

        # Apply transformation
        return self._transform_value(raw_value, partner)

    def _get_field_value(self, partner, field_path):
        """
        Navigate a dot-separated field path on the partner record.

        Args:
            partner: res.partner record
            field_path: Field path like 'name' or 'parent_id.name'

        Returns:
            Field value or None
        """
        try:
            value = partner
            for field_name in field_path.split("."):
                if not value:
                    return None
                value = value[field_name]
            return value
        except (KeyError, AttributeError) as e:
            _logger.warning("Failed to get field '%s' from partner %s: %s", field_path, partner.id, str(e))
            return None

    def _transform_value(self, value, partner):
        """
        Apply the configured transformation to the raw value.

        Args:
            value: Raw field value
            partner: res.partner record (for context in CEL expressions)

        Returns:
            Transformed value
        """
        if self.transform_type == "direct":
            return value

        elif self.transform_type == "date_yyyymmdd":
            return self._transform_date_yyyymmdd(value)

        elif self.transform_type == "gender_code":
            return self._transform_gender_code(value)

        elif self.transform_type == "address_combined":
            return self._transform_address_combined(partner)

        elif self.transform_type == "cel":
            return self._transform_cel(value, partner)

        else:
            _logger.warning("Unknown transform type: %s", self.transform_type)
            return value

    def _transform_date_yyyymmdd(self, value):
        """Convert date to ISO format string (YYYY-MM-DD).

        Note: Despite the method name, claim169 library expects ISO format
        with hyphens (e.g., "1984-04-18"), not compact YYYYMMDD.
        """
        if not value:
            return None

        # Handle both date and datetime objects
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                _logger.warning("Invalid date string: %s", value)
                return None

        if hasattr(value, "year"):
            # Return ISO format string as expected by claim169 library
            return value.strftime("%Y-%m-%d")

        return None

    def _transform_gender_code(self, value):
        """
        Transform gender to Claim 169 codes.

        Codes: 1=Male, 2=Female, 3=Others
        """
        if not value:
            return None

        value_lower = str(value).lower()

        if value_lower in ("male", "m", "1"):
            return 1
        elif value_lower in ("female", "f", "2"):
            return 2
        else:
            return 3

    def _transform_address_combined(self, partner):
        """Combine address fields into single string."""
        parts = []

        if partner.street:
            parts.append(partner.street)
        if partner.street2:
            parts.append(partner.street2)
        if partner.city:
            parts.append(partner.city)
        if partner.state_id:
            parts.append(partner.state_id.name)
        if partner.zip:
            parts.append(partner.zip)
        if partner.country_id:
            parts.append(partner.country_id.name)

        return ", ".join(parts) if parts else None

    def _transform_cel(self, value, partner):
        """Apply CEL expression transformation.

        Uses spp.cel.service to evaluate expressions like:
        - str(value).upper() - uppercase the value
        - str(value)[:10] - first 10 chars
        - value if value else "N/A" - default value

        Args:
            value: The raw field value to transform
            partner: res.partner record for context

        Returns:
            Transformed value, or original value on error
        """
        if not self.cel_expression:
            return value

        CelService = self.env.get("spp.cel.service")
        if not CelService:
            _logger.warning(
                "CEL service not available (spp_cel_domain not installed), " "returning raw value for expression: %s",
                self.cel_expression,
            )
            return value

        try:
            # Build context with the value and partner record
            # Access as: value, partner.name, partner.birthdate, etc.
            context = {
                "value": value,
                "partner": partner,
                "r": partner,  # Standard CEL alias
            }
            result = CelService.evaluate_expression(self.cel_expression, context)
            return result
        except Exception as e:
            _logger.error(
                "CEL evaluation failed for '%s': %s. Returning raw value.",
                self.cel_expression,
                str(e),
            )
            return value
