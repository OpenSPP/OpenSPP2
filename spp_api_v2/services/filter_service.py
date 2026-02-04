# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for parsing and executing filter queries."""

import logging
import re
from typing import Any

from odoo.api import Environment
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Regex pattern for parsing filter parameters with operators
# Matches: field[operator]=value or field.nested[operator]=value
FILTER_PARAM_PATTERN = re.compile(r"^(.+?)\[(\w+)\]$")

# SECURITY: Whitelist of models that can be filtered via custom filters
# Only these models are accessible when allow_custom_filters=True
ALLOWED_FILTER_MODELS = frozenset(
    [
        "res.partner",
        "spp.program",
        "spp.program.membership",
        "spp.registry.id",
        "spp.consent",
        "res.country",
        "res.country.state",
    ]
)

# SECURITY: Blacklist of sensitive field names/patterns
# These fields are NEVER accessible via custom filters
SENSITIVE_FIELD_PATTERNS = frozenset(
    [
        "password",
        "client_secret",
        "api_key",
        "token",
        "secret",
        "credential",
        "jwt",
        "oauth",
        "__",  # Magic fields
        "create_uid",  # Audit fields that could leak user info
        "write_uid",
    ]
)


class FilterService:
    """
    Service for parsing filter parameters and generating Odoo domains.

    Supports:
    - URL query parameter syntax: field[operator]=value
    - JSON body filters with complex AND/OR logic
    - Nested field filtering: relation.field
    - Filter presets
    """

    def __init__(self, env: Environment):
        self.env = env

    def get_path_config(self, resource_name: str):
        """
        Get the API path configuration for a resource.

        Args:
            resource_name: API resource name (e.g., 'Individual', 'Group')

        Returns:
            spp.api.path record or None
        """
        # Path configuration is public metadata - users need to see available filters
        # Use with_context to avoid triggering access checks on filter lookup
        return self.env["spp.api.path"].search(
            [("name", "=", resource_name), ("active", "=", True)],
            limit=1,
        )

    def parse_query_params(
        self,
        params: dict[str, Any],
        resource_name: str,
        api_client: Any = None,
    ) -> list:
        """
        Parse URL query parameters into Odoo domain.

        Supports:
        - Simple syntax: ?field=value (uses default operator)
        - Operator syntax: ?field[operator]=value
        - Nested fields: ?relation.field[operator]=value

        Args:
            params: Dictionary of query parameters
            resource_name: API resource name for filter lookup
            api_client: Optional API client for permission checks

        Returns:
            List of domain tuples
        """
        path_config = self.get_path_config(resource_name)
        if not path_config:
            _logger.warning("No path configuration found for resource: %s", resource_name)
            return []

        domain = []
        filters_by_name = {f.name: f for f in path_config.get_available_filters(api_client)}

        # Reserved parameters that are not filters
        reserved_params = {
            "_count",
            "_offset",
            "_sort",
            "_elements",
            "_extensions",
            "preset",
        }

        for param_key, param_value in params.items():
            if param_key in reserved_params or param_value is None:
                continue

            # Parse parameter to extract field name and operator
            field_name, operator = self._parse_param_key(param_key)

            # Look up filter configuration
            filter_config = filters_by_name.get(field_name)

            if filter_config:
                # Use configured filter
                try:
                    filter_domain = filter_config.to_domain(param_value, operator)
                    domain.extend(filter_domain)
                except ValidationError as e:
                    _logger.warning(
                        "Invalid filter value for %s: %s",
                        field_name,
                        str(e),
                    )
            elif path_config.allow_custom_filters:
                # Allow custom filters if enabled
                filter_domain = self._build_custom_domain(
                    field_name,
                    operator,
                    param_value,
                    path_config.model_id.model,
                )
                domain.extend(filter_domain)
            else:
                _logger.debug(
                    "Unknown filter parameter '%s' for resource %s",
                    field_name,
                    resource_name,
                )

        return domain

    def parse_json_filters(
        self,
        filters: list[dict],
        resource_name: str,
        api_client: Any = None,
        filter_logic: str = "AND",
    ) -> list:
        """
        Parse JSON filter array into Odoo domain.

        Supports:
        - Simple filters: {"field": "age", "operator": "gte", "value": 18}
        - Compound filters: {"logic": "OR", "conditions": [...]}
        - Nested AND/OR logic

        Args:
            filters: List of filter dictionaries
            resource_name: API resource name
            api_client: Optional API client for permission checks
            filter_logic: Top-level logic ("AND" or "OR")

        Returns:
            List of domain tuples
        """
        path_config = self.get_path_config(resource_name)
        if not path_config:
            return []

        return self.filters_to_domain(filters, path_config, api_client, filter_logic)

    def filters_to_domain(
        self,
        filters: list[dict],
        path_config,
        api_client: Any = None,
        filter_logic: str = "AND",
    ) -> list:
        """
        Convert a list of filter dictionaries to Odoo domain.

        Args:
            filters: List of filter dictionaries
            path_config: spp.api.path record
            api_client: Optional API client
            filter_logic: Top-level logic

        Returns:
            List of domain tuples
        """
        if not filters:
            return []

        filters_by_name = {f.name: f for f in path_config.get_available_filters(api_client)}
        domain_parts = []

        for condition in filters:
            if "logic" in condition:
                # Compound condition with nested logic
                nested_domain = self._parse_compound_condition(
                    condition,
                    filters_by_name,
                    path_config,
                )
                if nested_domain:
                    domain_parts.append(nested_domain)
            else:
                # Simple condition
                field = condition.get("field")
                operator = condition.get("operator", "eq")
                value = condition.get("value")

                filter_config = filters_by_name.get(field)
                if filter_config:
                    try:
                        filter_domain = filter_config.to_domain(value, operator)
                        domain_parts.extend(filter_domain)
                    except ValidationError as e:
                        _logger.warning(
                            "Invalid filter condition for %s: %s",
                            field,
                            str(e),
                        )
                elif path_config.allow_custom_filters:
                    custom_domain = self._build_custom_domain(
                        field,
                        operator,
                        value,
                        path_config.model_id.model,
                    )
                    domain_parts.extend(custom_domain)

        # Combine with appropriate logic
        if filter_logic == "OR" and len(domain_parts) > 1:
            # Add OR operators
            return self._combine_with_or(domain_parts)

        return domain_parts

    def apply_preset(
        self,
        preset_name: str,
        resource_name: str,
        additional_filters: list[dict] | None = None,
        api_client: Any = None,
    ) -> list:
        """
        Apply a saved filter preset and combine with additional filters.

        Args:
            preset_name: Name of the preset to apply
            resource_name: API resource name
            additional_filters: Optional additional filter conditions
            api_client: Optional API client

        Returns:
            Combined domain list
        """
        path_config = self.get_path_config(resource_name)
        if not path_config:
            return []

        # Find the preset - presets are public configurations, no sudo needed
        preset = self.env["spp.api.filter.preset"].search(
            [
                ("path_id", "=", path_config.id),
                ("name", "=", preset_name),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not preset:
            _logger.warning("Preset '%s' not found for resource %s", preset_name, resource_name)
            return []

        # Check if preset is accessible
        if not preset.is_public:
            _logger.warning("Preset '%s' is not public", preset_name)
            return []

        # Get preset domain
        preset_filters = preset.get_filters()
        domain = self.filters_to_domain(preset_filters, path_config, api_client)

        # Add additional filters
        if additional_filters:
            additional_domain = self.filters_to_domain(additional_filters, path_config, api_client)
            domain.extend(additional_domain)

        return domain

    def get_filter_metadata(self, resource_name: str, api_client: Any = None) -> dict:
        """
        Get metadata about available filters for a resource.

        Args:
            resource_name: API resource name
            api_client: Optional API client for permission-filtered results

        Returns:
            Dictionary with filter and preset metadata
        """
        path_config = self.get_path_config(resource_name)
        if not path_config:
            return {
                "resource": resource_name,
                "filters": [],
                "presets": [],
            }

        # Get available filters
        filters = path_config.get_available_filters(api_client)
        filter_metadata = [f.to_metadata() for f in filters]

        # Get available presets
        presets = path_config.get_available_presets(api_client)
        preset_metadata = [p.to_metadata() for p in presets]

        return {
            "resource": resource_name,
            "allow_custom_filters": path_config.allow_custom_filters,
            "max_filter_complexity": path_config.max_filter_complexity,
            "filters": filter_metadata,
            "presets": preset_metadata,
        }

    def validate_filter_complexity(
        self,
        filters: list[dict],
        resource_name: str,
    ) -> tuple[bool, str | None]:
        """
        Validate that filter complexity doesn't exceed limits.

        Args:
            filters: List of filter conditions
            resource_name: API resource name

        Returns:
            Tuple of (is_valid, error_message)
        """
        path_config = self.get_path_config(resource_name)
        if not path_config:
            return True, None

        # Count total conditions
        count = self._count_conditions(filters)
        max_complexity = path_config.max_filter_complexity

        if count > max_complexity:
            return (
                False,
                f"Filter complexity ({count}) exceeds maximum ({max_complexity})",
            )

        return True, None

    def _count_conditions(self, filters: list[dict]) -> int:
        """Recursively count the number of filter conditions."""
        count = 0
        for condition in filters:
            if "logic" in condition:
                # Compound condition - count nested conditions
                nested_conditions = condition.get("conditions", [])
                count += self._count_conditions(nested_conditions)
            else:
                count += 1
        return count

    def _parse_param_key(self, param_key: str) -> tuple[str, str | None]:
        """
        Parse parameter key to extract field name and operator.

        Examples:
            "age[gte]" -> ("age", "gte")
            "name" -> ("name", None)
            "partner_id.city[ilike]" -> ("partner_id.city", "ilike")

        Returns:
            Tuple of (field_name, operator)
        """
        match = FILTER_PARAM_PATTERN.match(param_key)
        if match:
            return match.group(1), match.group(2)
        return param_key, None

    def _parse_compound_condition(
        self,
        condition: dict,
        filters_by_name: dict,
        path_config,
    ) -> list:
        """
        Parse a compound condition with AND/OR logic.

        Args:
            condition: Compound condition dict with 'logic' and 'conditions'
            filters_by_name: Dictionary of available filters
            path_config: Path configuration

        Returns:
            Domain with appropriate OR operators prepended
        """
        logic = condition.get("logic", "AND")
        nested_conditions = condition.get("conditions", [])

        if not nested_conditions:
            return []

        # Build domain for each nested condition
        nested_domains = []
        for nested in nested_conditions:
            if "logic" in nested:
                # Recursive compound
                nested_domain = self._parse_compound_condition(
                    nested,
                    filters_by_name,
                    path_config,
                )
                if nested_domain:
                    nested_domains.append(nested_domain)
            else:
                field = nested.get("field")
                operator = nested.get("operator", "eq")
                value = nested.get("value")

                filter_config = filters_by_name.get(field)
                if filter_config:
                    try:
                        filter_domain = filter_config.to_domain(value, operator)
                        nested_domains.extend(filter_domain)
                    except ValidationError as e:
                        _logger.warning(
                            "Invalid filter condition for field %s: %s",
                            field,
                            str(e),
                        )
                elif path_config.allow_custom_filters:
                    custom_domain = self._build_custom_domain(
                        field,
                        operator,
                        value,
                        path_config.model_id.model,
                    )
                    nested_domains.extend(custom_domain)

        if logic == "OR":
            return self._combine_with_or(nested_domains)

        return nested_domains

    def _combine_with_or(self, domain_parts: list) -> list:
        """
        Combine domain parts with OR operators.

        Odoo domain uses Polish notation, so for N conditions we need N-1 OR operators.

        Example:
            [(a), (b), (c)] -> ['|', '|', (a), (b), (c)]

        For nested domains (already combined), we need to count domain "units":
        - A tuple like ('field', '=', 'value') counts as 1 unit
        - An already-combined domain like ['|', (a), (b)] counts as 1 unit
        """
        if not domain_parts:
            return []
        if len(domain_parts) == 1:
            if isinstance(domain_parts[0], list):
                return domain_parts[0]
            return domain_parts

        # Separate the domain into individual conditions
        # Each condition is either a tuple or a nested list that's already combined
        conditions = []
        i = 0
        while i < len(domain_parts):
            part = domain_parts[i]
            if isinstance(part, tuple):
                conditions.append([part])
                i += 1
            elif isinstance(part, list):
                # This is a nested domain, treat it as a single condition
                conditions.append(part)
                i += 1
            elif part == "|":
                # Skip OR operators - we'll add our own
                i += 1
            else:
                i += 1

        if len(conditions) <= 1:
            return conditions[0] if conditions else []

        # Combine all conditions with OR using Polish notation
        # For N conditions, we need N-1 OR operators at the front
        result = ["|"] * (len(conditions) - 1)
        for cond in conditions:
            result.extend(cond)

        return result

    def _is_sensitive_field(self, field_name: str) -> bool:
        """
        Check if a field name matches sensitive patterns.

        SECURITY: Prevents access to password, token, and other sensitive fields.
        """
        field_lower = field_name.lower()
        for pattern in SENSITIVE_FIELD_PATTERNS:
            if pattern in field_lower:
                return True
        return False

    def _validate_field_path(self, field_path: str, model_name: str) -> bool:
        """
        Validate that a field path exists on the model and is safe to access.

        SECURITY: Prevents SQL injection and access to unauthorized fields.
        Implements:
        1. Model whitelist - only allowed models can be filtered
        2. Field blacklist - sensitive fields are never accessible
        3. Format validation - alphanumeric, underscores, dots only

        Args:
            field_path: Dot-separated field path (e.g., "partner_id.name")
            model_name: Base model name

        Returns:
            True if field path is valid and safe, False otherwise
        """
        if not field_path or not model_name:
            return False

        # SECURITY: Check model is in whitelist
        if model_name not in ALLOWED_FILTER_MODELS:
            _logger.warning(
                "SECURITY: Rejecting filter on non-whitelisted model: %s",
                model_name,
            )
            return False

        # Validate field path format (alphanumeric, underscores, and dots only)
        if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$", field_path, re.IGNORECASE):
            _logger.warning("Invalid field path format: %s", field_path)
            return False

        # SECURITY: Check for sensitive field patterns in the full path
        if self._is_sensitive_field(field_path):
            _logger.warning(
                "SECURITY: Rejecting filter on sensitive field: %s",
                field_path,
            )
            return False

        # Check that the model exists
        if model_name not in self.env:
            _logger.warning("Model not found: %s", model_name)
            return False

        # Validate each part of the field path
        parts = field_path.split(".")
        current_model = self.env[model_name]

        for i, part in enumerate(parts):
            # SECURITY: Check each field part for sensitive patterns
            if self._is_sensitive_field(part):
                _logger.warning(
                    "SECURITY: Rejecting filter on sensitive field part: %s",
                    part,
                )
                return False

            if part not in current_model._fields:
                _logger.warning(
                    "Field '%s' not found on model %s (path: %s)",
                    part,
                    current_model._name,
                    field_path,
                )
                return False

            field = current_model._fields[part]

            # If not the last part, traverse to the related model
            if i < len(parts) - 1:
                if field.type not in ("many2one", "one2many", "many2many"):
                    _logger.warning(
                        "Cannot traverse through non-relational field '%s' (type: %s)",
                        part,
                        field.type,
                    )
                    return False
                comodel_name = field.comodel_name
                if comodel_name not in self.env:
                    _logger.warning("Related model '%s' not found", comodel_name)
                    return False
                # SECURITY: Check related model is in whitelist
                if comodel_name not in ALLOWED_FILTER_MODELS:
                    _logger.warning(
                        "SECURITY: Rejecting traverse to non-whitelisted model: %s",
                        comodel_name,
                    )
                    return False
                current_model = self.env[comodel_name]

        return True

    def _build_custom_domain(
        self,
        field_path: str,
        operator: str | None,
        value: Any,
        model_name: str,
    ) -> list:
        """
        Build domain for custom (non-configured) filters.

        Args:
            field_path: Odoo field path
            operator: Filter operator
            value: Filter value
            model_name: Model name for type inference

        Returns:
            List of domain tuples
        """
        # SECURITY: Validate field path exists on the model
        if not self._validate_field_path(field_path, model_name):
            _logger.warning(
                "Rejecting invalid field path '%s' for model %s",
                field_path,
                model_name,
            )
            return []

        # Map operator to Odoo domain operator
        operator_map = {
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
            None: "=",  # Default
        }

        odoo_op = operator_map.get(operator, "=")

        # Handle special operators
        if operator == "null":
            is_null = str(value).lower() in ("true", "1", "yes")
            return [(field_path, "=" if is_null else "!=", False)]

        if operator in ("in", "nin"):
            if isinstance(value, str):
                values = [v.strip() for v in value.split(",")]
            else:
                values = list(value) if isinstance(value, list | tuple) else [value]
            return [(field_path, odoo_op, values)]

        return [(field_path, odoo_op, value)]
