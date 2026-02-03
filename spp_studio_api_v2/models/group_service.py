# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend GroupService with extension write support and variable values."""

import logging
from typing import Any

from odoo import api, models

_logger = logging.getLogger(__name__)


class StudioGroupServiceMixin(models.AbstractModel):
    """Mixin providing Studio API functionality for Group resources.

    This model provides methods that can be called from GroupService
    to handle extension writes and variable values.
    """

    _name = "spp.studio.api.group.mixin"
    _description = "Studio API Group Mixin"

    @api.model
    def parse_extension_data(self, ext_data: dict, resource_type: str = "group") -> dict:
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
        """Get cached variable values for a group.

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


# Monkey-patch GroupService to support extensions
def _patch_group_service():
    """Patch GroupService to handle extension writes and variable values."""
    try:
        from odoo.addons.spp_api_v2.services.group_service import GroupService

        # Store original methods
        _original_from_api_schema = GroupService.from_api_schema
        _original_to_api_schema = GroupService.to_api_schema

        def from_api_schema_with_extensions(self, schema):
            """Extended from_api_schema that handles extension data."""
            vals = _original_from_api_schema(self, schema)

            # Process extension data if present
            if hasattr(schema, "extension") and schema.extension:
                try:
                    mixin = self.env["spp.studio.api.group.mixin"]
                    ext_vals = mixin.parse_extension_data(schema.extension, "group")
                    vals.update(ext_vals)
                    _logger.debug(
                        "Parsed extension data for group: %s",
                        list(ext_vals.keys()),
                    )
                except (KeyError, ValueError, TypeError) as e:
                    _logger.warning("Failed to parse extension data: %s", e)

            return vals

        def to_api_schema_with_variables(self, group, extensions=None, **kwargs):
            """Extended to_api_schema that includes variable values.

            Args:
                group: res.partner (group) record
                extensions: Optional extension data
                **kwargs: Additional options:
                    - include_variables: List of variable names or ["*"] for all
                    - variable_period: Period key (default: "current")
            """
            # Call original method
            data = _original_to_api_schema(self, group, extensions)

            # Add variable values if requested
            include_variables = kwargs.get("include_variables")
            variable_period = kwargs.get("variable_period", "current")

            if include_variables and group:
                try:
                    mixin = self.env["spp.studio.api.group.mixin"]
                    var_names = include_variables if include_variables != ["*"] else None
                    var_data = mixin.get_variable_values(
                        group.id,
                        var_names,
                        variable_period,
                    )
                    if var_data:
                        data["computedData"] = var_data
                except (KeyError, ValueError, TypeError) as e:
                    _logger.warning("Failed to get variable values: %s", e)

            return data

        # Apply patches
        GroupService.from_api_schema = from_api_schema_with_extensions
        GroupService.to_api_schema = to_api_schema_with_variables

        _logger.info("GroupService patched with extension and variable support")

    except ImportError:
        _logger.debug("spp_api_v2 not installed, skipping GroupService patch")
    except AttributeError as e:
        _logger.warning("Failed to patch GroupService: missing attribute %s", e)


# Apply patch when module loads
_patch_group_service()
