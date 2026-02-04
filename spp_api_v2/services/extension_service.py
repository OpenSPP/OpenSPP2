# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for handling API extensions"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ExtensionService:
    """Service for mapping extension data to API format"""

    def __init__(self, env: Environment):
        self.env = env

    def get_extension_data(
        self, partner, extension_names: list[str], resource_type: str = "individual"
    ) -> dict[str, Any]:
        """
        Get extension data for a partner.

        Args:
            partner: res.partner record
            extension_names: List of extension names/URLs to include (or ["*"] for all)
            resource_type: 'individual' or 'group'

        Returns:
            Dictionary mapping extension names to their data
            Format: {
                "farmer": {
                    "url": "urn:openspp:extension:farmer",
                    "farmSize": 2.5,
                    "farmSizeUnit": "hectares",
                    ...
                }
            }
        """
        if not extension_names:
            return {}

        # Get all applicable extensions (use sudo() for permission)
        all_extensions = self.env["spp.api.extension"].sudo().get_extensions_for_resource(resource_type)

        # Determine which extensions to include
        if "*" in extension_names:
            extensions_to_include = all_extensions
        else:
            # Filter to requested extensions (by name, URL, or derived key)
            extensions_to_include = all_extensions.filtered(
                lambda e: e.name in extension_names
                or e.url in extension_names
                or self._get_extension_key(e) in extension_names
            )

        if not extensions_to_include:
            _logger.debug("No extensions found for %s", extension_names)
            return {}

        # Build extension data
        result = {}
        for extension in extensions_to_include:
            extension_data = self._map_extension_fields(partner, extension)
            if extension_data:
                # Use extension name as key (not full URL)
                extension_key = self._get_extension_key(extension)
                result[extension_key] = {
                    "url": extension.url,
                    **extension_data,
                }

        return result

    def _get_extension_key(self, extension):
        """
        Get the key name for an extension from its URL.

        Converts urn:openspp:extension:farmer -> "farmer"
        """
        # If URL is a URN, extract the last part
        url = extension.url
        if url.startswith("urn:"):
            parts = url.split(":")
            if len(parts) >= 4:
                return parts[-1]
        # Otherwise use the extension name (lowercase, no spaces)
        return extension.name.lower().replace(" ", "_")

    def _map_extension_fields(self, partner, extension) -> dict[str, Any]:
        """
        Map Odoo fields to API extension format.

        Args:
            partner: res.partner record
            extension: spp.api.extension record

        Returns:
            Dictionary of field name -> value in API format
        """
        result = {}

        for field in extension.field_ids:
            # Get Odoo value
            odoo_value = getattr(partner, field.name, None)

            # Skip if value is None (field not set on this record).
            if odoo_value is None:
                continue

            # For relational fields, skip empty recordsets
            if field.ttype in ("many2one", "many2many", "one2many") and not odoo_value:
                continue

            # Convert field name to API format (camelCase)
            api_name = self._odoo_to_api_field_name(field.name)

            # Convert value based on field type
            api_value = self._convert_field_value(field, odoo_value)

            if api_value is not None:
                result[api_name] = api_value

        return result

    def _odoo_to_api_field_name(self, odoo_name: str) -> str:
        """
        Convert Odoo field name to API field name (camelCase).

        Examples:
            x_farm_size -> farmSize
            x_primary_crop_id -> primaryCrop
            farm_size -> farmSize

        Args:
            odoo_name: Odoo field name (e.g., x_farm_size)

        Returns:
            API field name in camelCase (e.g., farmSize)
        """
        # Remove x_ prefix if present
        name = odoo_name[2:] if odoo_name.startswith("x_") else odoo_name

        # Remove _id suffix for Many2one fields
        if name.endswith("_id"):
            name = name[:-3]

        # Convert snake_case to camelCase
        parts = name.split("_")
        if not parts:
            return name

        # First part stays lowercase, rest are capitalized
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def _convert_field_value(self, field, odoo_value) -> Any:
        """
        Convert Odoo field value to API format.

        Handles:
        - Many2one fields with namespace_uri (vocabulary codes) -> CodeableConcept
        - Regular Many2one -> Just the display name
        - Other types -> Native value

        Args:
            field: ir.model.fields record
            odoo_value: The value from Odoo

        Returns:
            Value in API format
        """
        if field.ttype == "many2one":
            # Check if this is a vocabulary code (has namespace_uri)
            if odoo_value and hasattr(odoo_value, "namespace_uri"):
                # This is a vocabulary code - return as CodeableConcept
                # Note: spp.vocabulary.code uses 'display' not 'name'
                display_value = odoo_value.display or odoo_value.code
                return {
                    "coding": [
                        {
                            "system": odoo_value.namespace_uri,
                            "code": odoo_value.code,
                            "display": display_value,
                        }
                    ],
                    "text": display_value,
                }
            elif odoo_value:
                # Regular Many2one - just return the display name
                return odoo_value.display_name

        elif field.ttype == "many2many":
            # Return list of values
            if odoo_value:
                # Check if items have namespace_uri (vocabulary codes)
                # We check the first item and assume homogeneous recordset
                if odoo_value and hasattr(odoo_value[0], "namespace_uri"):
                    result = []
                    for item in odoo_value:
                        if hasattr(item, "namespace_uri") and item.namespace_uri:
                            # Note: spp.vocabulary.code uses 'display' not 'name'
                            result.append(
                                {
                                    "coding": [
                                        {
                                            "system": item.namespace_uri,
                                            "code": item.code,
                                            "display": item.display or item.code,
                                        }
                                    ]
                                }
                            )
                        else:
                            # Fallback for items without namespace_uri
                            result.append(item.display_name)
                    return result
                else:
                    return [item.display_name for item in odoo_value]

        elif field.ttype == "one2many":
            # Skip one2many fields - too complex for simple extension
            _logger.debug("Skipping one2many field: %s", field.id)
            return None

        elif field.ttype == "date":
            # Convert date to ISO format
            return odoo_value.isoformat() if odoo_value else None

        elif field.ttype == "datetime":
            # Convert datetime to ISO format
            return odoo_value.isoformat() if odoo_value else None

        elif field.ttype == "boolean":
            return bool(odoo_value)

        elif field.ttype in ("integer", "float", "monetary"):
            return odoo_value

        elif field.ttype in ("char", "text", "html"):
            return str(odoo_value) if odoo_value else None

        elif field.ttype == "selection":
            # Return the value (not the display name)
            return odoo_value

        # For any other types, return as-is
        return odoo_value
