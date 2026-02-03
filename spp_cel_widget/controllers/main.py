"""CEL Widget HTTP Controllers."""

import logging
import re

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Validation constants
MAX_EXPRESSION_LENGTH = 10000
PROFILE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def _validate_profile_name(profile):
    """Validate profile name to prevent injection attacks."""
    if not profile or not isinstance(profile, str):
        raise UserError("Profile name is required")
    if len(profile) > 100:
        raise UserError("Profile name too long (max 100 characters)")
    if not PROFILE_NAME_PATTERN.match(profile):
        raise UserError("Invalid profile name format")
    return profile


def _validate_expression(expression):
    """Validate expression input."""
    if expression is None:
        return ""
    if not isinstance(expression, str):
        raise UserError("Expression must be a string")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise UserError(f"Expression too long (max {MAX_EXPRESSION_LENGTH} characters)")
    return expression


class CelWidgetController(http.Controller):
    """HTTP endpoints for CEL expression widget."""

    @http.route("/spp_cel/symbols/<string:profile>", type="jsonrpc", auth="user", methods=["POST"])
    def get_symbols(self, profile):
        """Get symbols for a CEL profile.

        Args:
            profile: Profile name (e.g., "registry_individuals")

        Returns:
            JSON with variables, functions, operators, keywords
        """
        profile = _validate_profile_name(profile)
        provider = request.env["spp.cel.symbol.provider"]
        return provider.get_symbols_for_profile(profile)

    @http.route("/spp_cel/validate", type="jsonrpc", auth="user", methods=["POST"])
    def validate_expression(self, expression, profile, expression_type=None, output_type=None):
        """Validate a CEL expression.

        Args:
            expression: CEL expression string
            profile: Profile name
            expression_type: Type of expression (filter, formula, scoring, validation, other)
            output_type: Expected output type (boolean, number, string, money)

        Returns:
            JSON with valid, errors, warnings, matching_count, explain
        """
        profile = _validate_profile_name(profile)
        expression = _validate_expression(expression)
        provider = request.env["spp.cel.symbol.provider"]
        return provider.validate_expression(
            expression, profile, expression_type=expression_type, output_type=output_type
        )

    @http.route("/spp_cel/profiles", type="jsonrpc", auth="user", methods=["POST"])
    def get_profiles(self):
        """Get list of available CEL profiles.

        Returns:
            JSON list of profile info dicts
        """
        provider = request.env["spp.cel.symbol.provider"]
        return provider.get_available_profiles()
