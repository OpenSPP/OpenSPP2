# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for parsing API extension data into Odoo field values."""

import logging
import math
from typing import Any

from odoo import Command
from odoo.api import Environment

_logger = logging.getLogger(__name__)

# Models that are safe for display name lookup
SAFE_LOOKUP_MODELS = frozenset(
    {
        "spp.vocabulary.code",
        "spp.vocabulary",
        "res.country",
        "res.country.state",
        "res.partner.category",
    }
)

# Models that should NEVER be accessed
BLOCKED_MODELS = frozenset(
    {
        "res.users",
        "ir.config_parameter",
        "spp.api.client",
        "ir.cron",
        "ir.mail_server",
    }
)


class ExtensionWriteService:
    """Parse incoming API extension data into Odoo field values.

    Handles the reverse mapping from API format to Odoo format:
    - camelCase API names → snake_case Odoo field names
    - CodeableConcept → Many2one vocabulary lookups
    - ISO dates → Odoo date fields
    - Arrays of CodeableConcept → Many2many
    """

    def __init__(self, env: Environment):
        self.env = env

    def parse_extension_data(self, ext_data: dict[str, Any], resource_type: str) -> dict[str, Any]:
        """Convert incoming extension data to Odoo field values.

        Args:
            ext_data: Dictionary mapping extension keys to their field values
                      e.g., {"studio-individual": {"farmSize": 2.5, "primaryCrop": {...}}}
            resource_type: 'individual' or 'group'

        Returns:
            Dictionary of Odoo field names to values ready for create/write
        """
        if not ext_data:
            return {}

        vals = {}

        for ext_key, ext_values in ext_data.items():
            if not isinstance(ext_values, dict):
                _logger.warning("Extension '%s' has invalid value type", ext_key)
                continue

            # Find the extension by key or URL
            extension = self._find_extension(ext_key, resource_type)
            if not extension:
                _logger.debug(
                    "Extension '%s' not found for resource_type='%s'",
                    ext_key,
                    resource_type,
                )
                continue

            # Parse each field in the extension
            ext_vals = self._parse_extension_fields(extension, ext_values)
            vals.update(ext_vals)

        return vals

    def _find_extension(self, ext_key: str, resource_type: str):
        """Find an API extension by key or URL.

        Args:
            ext_key: Extension key (e.g., "studio-individual") or URL
            resource_type: 'individual' or 'group'

        Returns:
            spp.api.extension record or None
        """
        # sudo() required: Extension registry is system config, accessed by API
        # regardless of current user. Authorization is done at API scope level.
        Extension = self.env["spp.api.extension"].sudo()

        # Build domain based on resource type
        applies_domain = [("applies_to", "in", [resource_type, "both"])]

        # Try exact URL match first
        extension = Extension.search(
            [("url", "=", ext_key), ("active", "=", True)] + applies_domain,
            limit=1,
        )
        if extension:
            return extension

        # Try URL ending with ext_key
        extension = Extension.search(
            [("url", "=like", f"%:{ext_key}"), ("active", "=", True)] + applies_domain,
            limit=1,
        )
        if extension:
            return extension

        # Try by name (case-insensitive)
        extension = Extension.search(
            [("name", "ilike", ext_key), ("active", "=", True)] + applies_domain,
            limit=1,
        )

        return extension

    def _parse_extension_fields(self, extension, ext_values: dict[str, Any]) -> dict[str, Any]:
        """Parse field values for a specific extension.

        Args:
            extension: spp.api.extension record
            ext_values: Dictionary of API field names to values

        Returns:
            Dictionary of Odoo field names to converted values
        """
        vals = {}

        # Skip the 'url' key if present (it's metadata, not a field)
        field_values = {k: v for k, v in ext_values.items() if k != "url"}

        for field in extension.field_ids:
            # Convert Odoo field name to API format to find matching key
            api_name = self._odoo_to_api_name(field.name)

            if api_name not in field_values:
                continue

            api_value = field_values[api_name]

            # Convert API value to Odoo format
            odoo_value = self._convert_to_odoo(field, api_value)

            if odoo_value is not None:
                vals[field.name] = odoo_value
            elif api_value is None:
                # Explicitly set None/null values
                vals[field.name] = False

        return vals

    def _odoo_to_api_name(self, odoo_name: str) -> str:
        """Convert Odoo field name to API format (camelCase).

        Mirrors the logic in ExtensionService._odoo_to_api_field_name

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

        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    def _convert_to_odoo(self, field, api_value: Any) -> Any:
        """Convert API value to Odoo format based on field type.

        Args:
            field: ir.model.fields record
            api_value: Value from API request

        Returns:
            Converted value for Odoo create/write
        """
        if api_value is None:
            return None

        ttype = field.ttype

        if ttype == "many2one":
            return self._convert_many2one(field, api_value)

        elif ttype == "many2many":
            return self._convert_many2many(field, api_value)

        elif ttype in ("date", "datetime"):
            # Odoo accepts ISO format strings directly
            return api_value if isinstance(api_value, str) else None

        elif ttype == "boolean":
            # Handle string boolean values explicitly
            if isinstance(api_value, str):
                return api_value.lower() in ("true", "1", "yes")
            return bool(api_value)

        elif ttype == "integer":
            try:
                if isinstance(api_value, bool):
                    return 1 if api_value else 0
                val = int(api_value)
                # PostgreSQL integer range
                if val < -2147483648 or val > 2147483647:
                    _logger.warning("Integer value %s out of range", val)
                    return None
                return val
            except (ValueError, TypeError, OverflowError):
                _logger.warning("Cannot convert %r to integer", api_value)
                return None

        elif ttype == "float":
            try:
                if isinstance(api_value, bool):
                    return 1.0 if api_value else 0.0
                val = float(api_value)
                if not math.isfinite(val):
                    _logger.warning("Float value %s is not finite", val)
                    return None
                return val
            except (ValueError, TypeError, OverflowError):
                _logger.warning("Cannot convert %r to float", api_value)
                return None

        elif ttype in ("char", "text", "html"):
            return str(api_value) if api_value is not None else None

        elif ttype == "selection":
            # Selection values passed as-is
            return api_value

        # Default: pass through
        return api_value

    def _convert_many2one(self, field, api_value: Any) -> int | bool:
        """Convert Many2one field value from API format.

        Handles:
        - CodeableConcept: {"coding": [{"system": ..., "code": ...}]}
        - Simple ID reference: "namespace|value"
        - Display name lookup: "Some Name"

        Args:
            field: ir.model.fields record
            api_value: API value

        Returns:
            Record ID or False
        """
        if not api_value:
            return False

        relation = field.relation

        # Handle CodeableConcept format (vocabulary codes)
        if isinstance(api_value, dict) and "coding" in api_value:
            codings = api_value.get("coding", [])
            if codings and isinstance(codings, list):
                coding = codings[0]
                system = coding.get("system")
                code = coding.get("code")

                if system and code:
                    record = self._find_vocabulary_code(system, code)
                    if record:
                        return record.id

                # Fallback: try finding by display
                display = coding.get("display")
                if display and relation:
                    record = self._find_by_display(relation, display)
                    if record:
                        return record.id

            return False

        # Handle string value
        if isinstance(api_value, str):
            # Try namespace|value format
            if "|" in api_value:
                namespace, value = api_value.split("|", 1)
                record = self._find_vocabulary_code(namespace, value)
                if record:
                    return record.id

            # Try display name lookup
            if relation:
                record = self._find_by_display(relation, api_value)
                if record:
                    return record.id

        return False

    def _convert_many2many(self, field, api_value: Any) -> list:
        """Convert Many2many field value from API format.

        Args:
            field: ir.model.fields record
            api_value: API value (list of items)

        Returns:
            Odoo Command list for Many2many field
        """
        if not api_value or not isinstance(api_value, list):
            return [Command.clear()]

        ids = []
        relation = field.relation

        for item in api_value:
            record_id = None

            # Handle CodeableConcept in array
            if isinstance(item, dict) and "coding" in item:
                codings = item.get("coding", [])
                if codings:
                    coding = codings[0]
                    system = coding.get("system")
                    code = coding.get("code")
                    if system and code:
                        record = self._find_vocabulary_code(system, code)
                        if record:
                            record_id = record.id

            # Handle simple string
            elif isinstance(item, str):
                if "|" in item:
                    namespace, value = item.split("|", 1)
                    record = self._find_vocabulary_code(namespace, value)
                    if record:
                        record_id = record.id
                elif relation:
                    record = self._find_by_display(relation, item)
                    if record:
                        record_id = record.id

            if record_id:
                ids.append(record_id)

        if ids:
            return [Command.set(ids)]
        return [Command.clear()]

    def _find_vocabulary_code(self, system: str, code: str):
        """Find a vocabulary code by namespace_uri and code.

        Args:
            system: Namespace URI
            code: Code value

        Returns:
            spp.vocabulary.code record or None
        """
        if "spp.vocabulary.code" not in self.env:
            return None

        # sudo() required: Vocabulary lookup is system config, API needs access
        # to resolve CodeableConcept values regardless of user permissions.
        VocabCode = self.env["spp.vocabulary.code"].sudo()
        return VocabCode.search(
            [("namespace_uri", "=", system), ("code", "=", code)],
            limit=1,
        )

    def _find_by_display(self, model_name: str, display_name: str):
        """Find a record by display name.

        Args:
            model_name: Model name (e.g., 'res.country')
            display_name: Display name to search

        Returns:
            Record or None
        """
        # Security: Only allow lookups on safe models
        if model_name in BLOCKED_MODELS:
            _logger.warning("Blocked lookup attempt on sensitive model: %s", model_name)
            return None

        if model_name not in SAFE_LOOKUP_MODELS:
            _logger.debug("Model %s not in safe lookup list, skipping display lookup", model_name)
            return None

        try:
            # sudo() required: Display name lookups on safe reference models
            # (e.g., countries, categories) need system access. Model allowlist
            # above ensures only safe models are accessed.
            Model = self.env[model_name].sudo()
            # Try exact match first
            record = Model.search([("name", "=", display_name)], limit=1)
            if record:
                return record
            # Try case-insensitive
            record = Model.search([("name", "ilike", display_name)], limit=1)
            return record
        except Exception as e:
            _logger.debug("Could not find %s by display '%s': %s", model_name, display_name, e)
            return None
