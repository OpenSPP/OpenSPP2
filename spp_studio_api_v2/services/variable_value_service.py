# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for fetching variable values for API responses."""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)

# Models that are safe for variable computation
SAFE_SOURCE_MODELS = frozenset(
    {
        "res.partner",
        "spp.program.membership",
        "spp.entitlement",
    }
)

# Maximum batch size for bulk queries
MAX_BATCH_SIZE = 1000


class VariableValueService:
    """Fetch cached/computed variable values for API responses.

    Retrieves values from spp.data.value for inclusion in Individual/Group responses.
    Supports:
    - Specific variable selection
    - All cached values ("*")
    - Historical period queries
    """

    def __init__(self, env: Environment):
        self.env = env

    def get_values_for_subject(
        self,
        partner_id: int,
        variable_names: list[str] | None = None,
        period_key: str = "current",
        include_stale: bool = True,
    ) -> dict[str, Any]:
        """Get cached variable values for a subject.

        Args:
            partner_id: res.partner ID
            variable_names: List of variable names to include, or None/"*" for all
            period_key: Period key to query (default: "current")
            include_stale: Whether to include stale (expired but not refreshed) values

        Returns:
            Dictionary mapping variable names to their value details:
            {
                "variableName": {
                    "value": <any>,
                    "periodKey": "current",
                    "recordedAt": "2024-01-15T10:30:00",
                    "isStale": false,
                    "sourceType": "computed"
                }
            }
        """
        if "spp.data.value" not in self.env:
            _logger.debug("spp.data.value model not available")
            return {}
        DataValue = self.env["spp.data.value"]

        # Build domain
        domain = [
            ("subject_model", "=", "res.partner"),
            ("subject_id", "=", partner_id),
            ("period_key", "=", period_key),
        ]

        # Filter by variable names if specified
        if variable_names and "*" not in variable_names:
            domain.append(("variable_name", "in", variable_names))

        # Optionally exclude stale values
        if not include_stale:
            domain.append(("is_stale", "=", False))

        # Fetch values
        # sudo() required: Data values are computed system data, API needs
        # access regardless of user. Authorization is via API scope checks.
        values = DataValue.sudo().search(domain)  # nosemgrep: odoo-sudo-without-context

        result = {}
        for val in values:
            # Extract the actual value from value_json
            raw_value = val.value_json
            if isinstance(raw_value, dict) and "value" in raw_value:
                actual_value = raw_value["value"]
            else:
                actual_value = raw_value

            result[val.variable_name] = {
                "value": actual_value,
                "periodKey": val.period_key,
                "recordedAt": val.recorded_at.isoformat() if val.recorded_at else None,
                "isStale": val.is_stale,
                "sourceType": val.source_type,
            }

        return result

    def get_values_for_subjects(
        self,
        partner_ids: list[int],
        variable_names: list[str] | None = None,
        period_key: str = "current",
    ) -> dict[int, dict[str, Any]]:
        """Get cached variable values for multiple subjects (bulk).

        Args:
            partner_ids: List of res.partner IDs
            variable_names: List of variable names to include, or None/"*" for all
            period_key: Period key to query

        Returns:
            Dictionary mapping partner_id to variable values dict
        """
        if not partner_ids:
            return {}

        if len(partner_ids) > MAX_BATCH_SIZE:
            _logger.warning(
                "Batch size %d exceeds limit %d, truncating",
                len(partner_ids),
                MAX_BATCH_SIZE,
            )
            partner_ids = partner_ids[:MAX_BATCH_SIZE]

        if "spp.data.value" not in self.env:
            return {}
        DataValue = self.env["spp.data.value"]

        # Build domain
        domain = [
            ("subject_model", "=", "res.partner"),
            ("subject_id", "in", partner_ids),
            ("period_key", "=", period_key),
        ]

        if variable_names and "*" not in variable_names:
            domain.append(("variable_name", "in", variable_names))

        # sudo() required: Batch data value retrieval for API response
        values = DataValue.sudo().search(domain)  # nosemgrep: odoo-sudo-without-context

        # Group by subject_id
        result = {pid: {} for pid in partner_ids}

        for val in values:
            raw_value = val.value_json
            if isinstance(raw_value, dict) and "value" in raw_value:
                actual_value = raw_value["value"]
            else:
                actual_value = raw_value

            if val.subject_id in result:
                result[val.subject_id][val.variable_name] = {
                    "value": actual_value,
                    "periodKey": val.period_key,
                    "recordedAt": val.recorded_at.isoformat() if val.recorded_at else None,
                    "isStale": val.is_stale,
                    "sourceType": val.source_type,
                }

        return result

    def get_available_variables(
        self,
        resource_type: str = "both",
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        """Get list of available variables for a resource type.

        Args:
            resource_type: 'individual', 'group', or 'both'
            include_inactive: Whether to include inactive variables

        Returns:
            List of variable info dictionaries
        """
        if "spp.cel.variable" not in self.env:
            return []
        Variable = self.env["spp.cel.variable"]

        domain = []
        if not include_inactive:
            domain.append(("state", "=", "active"))

        if resource_type != "both":
            domain.append(("applies_to", "in", [resource_type, "both"]))

        # sudo() required: Variable definitions are system config, API needs
        # access to list available variables regardless of user permissions.
        # nosemgrep: odoo-sudo-without-context
        variables = Variable.sudo().search(domain, order="category_id, sequence, name")

        result = []
        for var in variables:
            info = {
                "name": var.cel_accessor,
                "label": getattr(var, "label", None) or var.name,
                "description": getattr(var, "description", None) or "",
                "valueType": var.value_type,
                "sourceType": var.source_type,
                "appliesTo": var.applies_to,
                "periodGranularity": var.period_granularity,
                "supportsHistorical": var.supports_historical,
            }

            # Include unit if available (from spp_studio extension)
            if hasattr(var, "unit") and var.unit:
                info["unit"] = var.unit

            # Include category if available
            if var.category_id:
                info["category"] = var.category_id.name

            result.append(info)

        return result

    def compute_variable_value(
        self,
        partner_id: int,
        variable_name: str,
        program_id: int | None = None,
    ) -> Any:
        """Compute a variable value on-demand (if computable).

        This is for variables that can be computed without caching.
        For cached variables, use get_values_for_subject.

        Args:
            partner_id: res.partner ID
            variable_name: Variable cel_accessor
            program_id: Optional program context for constant overrides

        Returns:
            Computed value or None if not computable
        """
        if "spp.cel.variable" not in self.env:
            return None
        Variable = self.env["spp.cel.variable"]

        # sudo() required: Variable definition lookup for computation
        variable = Variable.sudo().search(  # nosemgrep: odoo-sudo-without-context
            [("cel_accessor", "=", variable_name), ("state", "=", "active")],
            limit=1,
        )

        if not variable:
            _logger.debug("Variable '%s' not found or not active", variable_name)
            return None

        # Security: Only allow computation on safe models
        if variable.source_model not in SAFE_SOURCE_MODELS:
            _logger.warning("Blocked variable computation on model: %s", variable.source_model)
            return None

        # Only compute for field-type variables (direct field access)
        if variable.source_type == "field" and variable.source_model and variable.source_field:
            try:
                # sudo() required: Field value access on safe models (validated above)
                # for variable computation. SAFE_SOURCE_MODELS allowlist ensures
                # only appropriate models can be accessed.
                Model = self.env[variable.source_model].sudo()  # nosemgrep: odoo-sudo-without-context
                record = Model.browse(partner_id)
                if record.exists():
                    return getattr(record, variable.source_field, None)
            except Exception as e:
                _logger.warning(
                    "Failed to compute field variable '%s': %s",
                    variable_name,
                    e,
                )

        # For computed/aggregate variables, we'd need the CEL evaluator
        # which is out of scope for this service
        return None
