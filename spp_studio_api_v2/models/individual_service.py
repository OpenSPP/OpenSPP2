# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend IndividualService with extension write support and variable values."""

import logging
from typing import Any

from odoo import api, models

_logger = logging.getLogger(__name__)


class StudioIndividualServiceMixin(models.AbstractModel):
    """Mixin providing Studio API functionality for Individual resources.

    This model provides methods that can be called from IndividualService
    to handle extension writes and variable values.
    """

    _name = "spp.studio.api.individual.mixin"
    _description = "Studio API Individual Mixin"

    @api.model
    def parse_extension_data(self, ext_data: dict, resource_type: str = "individual") -> dict:
        """Parse incoming API extension data to Odoo field values.

        Args:
            ext_data: Extension data from API request
            resource_type: Resource type ('individual' or 'group')

        Returns:
            Dictionary of Odoo field names to values
        """
        from ..services.extension_write_service import ExtensionWriteService

        service = ExtensionWriteService(self.env)
        return service.parse_extension_data(ext_data, resource_type)

    @api.model
    def get_variable_values(
        self,
        partner_id: int,
        variable_names: list[str] | None = None,
        period_key: str = "current",
    ) -> dict[str, Any]:
        """Get cached variable values for a partner.

        Args:
            partner_id: res.partner ID
            variable_names: List of variable names or None/"*" for all
            period_key: Period key for historical queries

        Returns:
            Dictionary mapping variable names to value details
        """
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)
        return service.get_values_for_subject(partner_id, variable_names, period_key)

    @api.model
    def get_variable_values_bulk(
        self,
        partner_ids: list[int],
        variable_names: list[str] | None = None,
        period_key: str = "current",
    ) -> dict[int, dict[str, Any]]:
        """Get cached variable values for multiple partners.

        Args:
            partner_ids: List of res.partner IDs
            variable_names: List of variable names or None/"*" for all
            period_key: Period key for historical queries

        Returns:
            Dictionary mapping partner_id to variable values
        """
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)
        return service.get_values_for_subjects(partner_ids, variable_names, period_key)


# Monkey-patch IndividualService to support extensions
def _patch_individual_service():
    """Patch IndividualService to handle extension writes and variable values."""
    try:
        from odoo.addons.spp_api_v2.services.individual_service import IndividualService

        # Store original methods
        _original_from_api_schema = IndividualService.from_api_schema
        _original_to_api_schema = IndividualService.to_api_schema

        def from_api_schema_with_extensions(self, schema):
            """Extended from_api_schema that handles extension data."""
            vals = _original_from_api_schema(self, schema)

            # Process extension data if present
            if hasattr(schema, "extension") and schema.extension:
                try:
                    mixin = self.env["spp.studio.api.individual.mixin"]
                    ext_vals = mixin.parse_extension_data(schema.extension, "individual")
                    vals.update(ext_vals)
                    _logger.debug(
                        "Parsed extension data for individual: %s",
                        list(ext_vals.keys()),
                    )
                except (KeyError, ValueError, TypeError) as e:
                    _logger.warning("Failed to parse extension data: %s", e)

            return vals

        def to_api_schema_with_variables(self, partner, extensions=None, **kwargs):
            """Extended to_api_schema that includes variable values.

            Args:
                partner: res.partner record
                extensions: Optional extension data
                **kwargs: Additional options:
                    - include_variables: List of variable names or ["*"] for all
                    - variable_period: Period key (default: "current")
            """
            # Call original method
            data = _original_to_api_schema(self, partner, extensions)

            # Add variable values if requested
            include_variables = kwargs.get("include_variables")
            variable_period = kwargs.get("variable_period", "current")

            if include_variables and partner:
                try:
                    mixin = self.env["spp.studio.api.individual.mixin"]
                    var_names = include_variables if include_variables != ["*"] else None
                    var_data = mixin.get_variable_values(
                        partner.id,
                        var_names,
                        variable_period,
                    )
                    if var_data:
                        data["computedData"] = var_data
                except (KeyError, ValueError, TypeError) as e:
                    _logger.warning("Failed to get variable values: %s", e)

            return data

        # Apply patches
        IndividualService.from_api_schema = from_api_schema_with_extensions
        IndividualService.to_api_schema = to_api_schema_with_variables

        _logger.info("IndividualService patched with extension and variable support")

    except ImportError:
        _logger.debug("spp_api_v2 not installed, skipping IndividualService patch")
    except AttributeError as e:
        _logger.warning("Failed to patch IndividualService: missing attribute %s", e)


# Apply patch when module loads
_patch_individual_service()
