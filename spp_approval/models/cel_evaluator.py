"""CEL (Common Expression Language) evaluator for approval workflows.

This module uses spp_cel_domain's parser for CEL expression evaluation,
providing a lightweight solution without external dependencies.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Security: Fields that should never be exposed in CEL evaluation context
SENSITIVE_FIELDS = frozenset(
    {
        # Authentication/Security fields
        "password",
        "password_crypt",
        "totp_secret",
        "totp_trusted_device_ids",
        "api_key_ids",
        "oauth_uid",
        "oauth_access_token",
        # Session/Token fields
        "session_token",
        "access_token",
        "refresh_token",
        "auth_signup_token",
        "auth_signup_expiration",
        # Private keys and secrets
        "private_key",
        "secret_key",
        "api_secret",
        "encryption_key",
        # Credit/Banking info
        "credit_card",
        "card_number",
        "cvv",
        "bank_account",
        "iban",
        # Personal identifiers
        "ssn",
        "social_security",
        "national_id",
        "passport_number",
        # Odoo internal fields that could leak info
        "write_uid",
        "create_uid",
        "message_ids",
        "message_follower_ids",
        "activity_ids",
    }
)

# Security: Field name patterns that indicate sensitive data
SENSITIVE_FIELD_PATTERNS = (
    "password",
    "secret",
    "token",
    "key",
    "credential",
    "auth",
    "private",
    "encrypt",
)


class CELEvaluator(models.AbstractModel):
    """CEL expression evaluator service.

    Provides methods to evaluate CEL expressions in the context of
    Odoo records for approval workflow conditions.

    Usage:
        evaluator = self.env["spp.cel.evaluator"]
        result = evaluator.evaluate("record.amount > 1000", record)

    Available CEL Variables:
        - record: The Odoo record being evaluated
        - user: Current user (res.users)
        - company: Current company (res.company)
        - today: Current date (date)
        - now: Current datetime (datetime)

    CEL Functions:
        - has(value) or has(obj, field): Check if value/field is non-empty
        - size(collection): Get size of collection
        - matches(string, pattern): Regex matching
        - today(): Current date
        - now(): Current datetime
        - age_years(date): Calculate age in years
        - days_ago(n): Date n days ago
        - between(x, a, b): Check if a <= x <= b

    Operators:
        - Comparison: ==, !=, >, >=, <, <=
        - Logical: and, or, not
        - Membership: in (e.g., state in ['draft', 'pending'])
        - Unary: - (negation)
    """

    _name = "spp.cel.evaluator"
    _description = "CEL Expression Evaluator"

    @api.model
    def is_available(self):
        """Check if CEL evaluation is available.

        Always returns True since we use the built-in spp_cel_domain parser.
        """
        return True

    @api.model
    def evaluate(self, expression, record, extra_context=None):
        """Evaluate a CEL expression against a record.

        Args:
            expression: CEL expression string
            record: Odoo record to evaluate against
            extra_context: Optional dict of additional context variables

        Returns:
            Evaluation result (typically bool for conditions)

        Raises:
            ValidationError: If expression is invalid or evaluation fails
        """
        if not expression or not expression.strip():
            return True

        try:
            # Import parser from spp_cel_domain
            from odoo.addons.spp_cel_domain.services import cel_functions
            from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

            # Build context with record data and functions
            context = self._build_context(record, extra_context)

            # Add CEL functions to context
            context.update(
                {
                    "size": cel_functions.size,
                    "has": cel_functions.has,
                    "matches": cel_functions.matches,
                    "today": cel_functions.today,
                    "now": cel_functions.now,
                    "age_years": cel_functions.age_years,
                    "days_ago": cel_functions.days_ago,
                    "months_ago": cel_functions.months_ago,
                    "years_ago": cel_functions.years_ago,
                    "between": cel_functions.between,
                }
            )

            # Parse and evaluate
            ast = parse(expression)
            return evaluate(ast, context)

        except SyntaxError as e:
            _logger.error("CEL parse error for '%s': %s", expression, str(e))
            raise ValidationError(
                _("Invalid expression syntax '%(expr)s': %(error)s") % {"expr": expression, "error": str(e)}
            ) from e
        except Exception as e:
            _logger.error("CEL evaluation error for '%s': %s", expression, str(e))
            raise ValidationError(
                _("Error evaluating expression '%(expr)s': %(error)s") % {"expr": expression, "error": str(e)}
            ) from e

    @api.model
    def validate(self, expression):
        """Validate a CEL expression syntax.

        Args:
            expression: CEL expression string

        Returns:
            dict with 'valid' (bool) and 'error' (str or None)
        """
        if not expression or not expression.strip():
            return {"valid": True, "error": None}

        try:
            from odoo.addons.spp_cel_domain.services.cel_parser import parse

            parse(expression)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": str(e)}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    @api.model
    def evaluate_user_expression(self, expression, record, extra_context=None):
        """Evaluate a CEL expression that returns user IDs.

        Used for dynamic reviewer assignment.

        Args:
            expression: CEL expression that returns user ID(s)
            record: Odoo record context
            extra_context: Optional additional context

        Returns:
            res.users recordset
        """
        if not expression or not expression.strip():
            return self.env["res.users"]

        result = self.evaluate(expression, record, extra_context)

        # Handle different result types
        if isinstance(result, int):
            return self.env["res.users"].browse(result).exists()
        elif isinstance(result, list | tuple):
            user_ids = [uid for uid in result if isinstance(uid, int)]
            return self.env["res.users"].browse(user_ids).exists()
        elif hasattr(result, "_name") and result._name == "res.users":
            return result

        return self.env["res.users"]

    def _build_context(self, record, extra_context=None):
        """Build evaluation context from record.

        Args:
            record: Odoo record
            extra_context: Optional additional context dict

        Returns:
            dict of context variables
        """
        context = {
            # Core variables
            "record": self._record_to_dict(record),
            "user": self._record_to_dict(self.env.user),
            "company": self._record_to_dict(self.env.company),
            # Useful constants
            "true": True,
            "false": False,
            "null": None,
        }

        # Add extra context
        if extra_context:
            context.update(extra_context)

        return context

    def _is_sensitive_field(self, field_name):
        """Check if a field name indicates sensitive data.

        Args:
            field_name: Name of the field to check

        Returns:
            bool: True if the field is considered sensitive
        """
        # Direct match with known sensitive fields
        if field_name in SENSITIVE_FIELDS:
            return True

        # Check for sensitive patterns in field name
        field_lower = field_name.lower()
        for pattern in SENSITIVE_FIELD_PATTERNS:
            if pattern in field_lower:
                return True

        return False

    def _record_to_dict(self, record):
        """Convert Odoo record to dict for CEL evaluation.

        Args:
            record: Odoo record

        Returns:
            dict representation of record fields

        Security:
            - Private fields (starting with _) are excluded
            - Sensitive fields (passwords, tokens, etc.) are filtered out
            - Only safe field types are exposed
        """
        if not record:
            return {}

        result = {
            "id": record.id,
            "_name": record._name,
        }

        # Add common fields (if not sensitive)
        for field_name in ["name", "display_name", "state", "active"]:
            if field_name in record._fields and not self._is_sensitive_field(field_name):
                result[field_name] = getattr(record, field_name, None)

        # Add field values based on type
        for field_name, field in record._fields.items():
            # Security: Skip private fields
            if field_name.startswith("_"):
                continue

            # Security: Skip sensitive fields
            if self._is_sensitive_field(field_name):
                continue

            try:
                value = record[field_name]

                # Handle different field types
                if field.type in ("char", "text", "selection", "html"):
                    result[field_name] = value or ""
                elif field.type in ("integer", "float", "monetary"):
                    result[field_name] = value or 0
                elif field.type == "boolean":
                    result[field_name] = bool(value)
                elif field.type == "date":
                    result[field_name] = value
                elif field.type == "datetime":
                    result[field_name] = value
                elif field.type == "many2one":
                    result[field_name] = {
                        "id": value.id if value else 0,
                        "name": value.name if value and hasattr(value, "name") else "",
                    }
                elif field.type in ("one2many", "many2many"):
                    result[field_name] = {
                        "ids": value.ids,
                        "count": len(value),
                    }
            except Exception:
                # Skip fields that can't be read
                pass

        return result
