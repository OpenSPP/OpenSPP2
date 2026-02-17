# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Generic builder that converts an Odoo model's fields to JSON Schema 2020-12."""

import ast
import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)

# Field types that are always skipped (no meaningful JSON Schema representation)
SKIP_FIELD_TYPES = {"binary", "many2many", "one2many"}


class OdooModelSchemaBuilder:
    """Build a JSON Schema 2020-12 dict from an Odoo model's fields.

    Usage::

        builder = OdooModelSchemaBuilder(env)
        schema = builder.build_schema(
            env["res.partner"],
            skip_fields={"message_ids", "activity_ids"},
            title="Partner",
        )
    """

    def __init__(self, env: Environment):
        self.env = env

    def build_schema(
        self,
        model,
        *,
        skip_fields: set[str] | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Build JSON Schema 2020-12 from an Odoo model's fields.

        Args:
            model: An Odoo model recordset (e.g. ``env["res.partner"]``).
            skip_fields: Field names to exclude from the schema.
            title: Schema title. Falls back to the model's ``_description``.

        Returns:
            A dict representing a valid JSON Schema 2020-12 document.
        """
        skip = skip_fields or set()
        properties: dict[str, Any] = {}
        required: list[str] = []

        for field_name, field in model._fields.items():
            if field_name.startswith("_"):
                continue
            if field_name in skip:
                continue
            if not field.store:
                continue
            if field.type in SKIP_FIELD_TYPES:
                continue

            prop = self._field_to_property(field)
            if prop is None:
                continue

            # Standard metadata keywords
            if field.string:
                prop["title"] = field.string
            if field.help:
                prop["description"] = field.help
            if bool(field.readonly) or bool(field.compute):
                prop["readOnly"] = True

            properties[field_name] = prop

            if field.required:
                required.append(field_name)

        schema: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "title": title or getattr(model, "_description", model._name),
            "properties": properties,
        }
        if required:
            schema["required"] = sorted(required)

        return schema

    # ------------------------------------------------------------------
    # Field type mapping
    # ------------------------------------------------------------------

    def _field_to_property(self, field) -> dict[str, Any] | None:
        """Convert a single Odoo field to a JSON Schema property dict.

        Returns None if the field type is not supported.
        """
        handler = self._TYPE_HANDLERS.get(field.type)
        if handler is not None:
            return handler(self, field)

        # many2one requires special logic
        if field.type == "many2one":
            return self._handle_many2one(field)

        return None

    # --- simple types ---------------------------------------------------

    def _handle_char(self, field) -> dict[str, Any]:
        return {"type": "string"}

    def _handle_text(self, field) -> dict[str, Any]:
        return {"type": "string", "x-display": "multiline"}

    def _handle_integer(self, field) -> dict[str, Any]:
        return {"type": "integer"}

    def _handle_float(self, field) -> dict[str, Any]:
        return {"type": "number"}

    def _handle_boolean(self, field) -> dict[str, Any]:
        return {"type": "boolean"}

    def _handle_date(self, field) -> dict[str, Any]:
        return {"type": "string", "format": "date"}

    def _handle_datetime(self, field) -> dict[str, Any]:
        return {"type": "string", "format": "date-time"}

    # --- selection -------------------------------------------------------

    def _handle_selection(self, field) -> dict[str, Any]:
        choices = self._extract_selection_choices(field)
        if choices:
            return {"oneOf": [{"const": c["value"], "title": c["label"]} for c in choices]}
        return {"type": "string"}

    # --- many2one --------------------------------------------------------

    def _handle_many2one(self, field) -> dict[str, Any]:
        if field.comodel_name == "spp.vocabulary.code":
            return self._handle_vocabulary(field)
        return {
            "anyOf": [{"type": "string"}, {"type": "integer"}],
            "x-field-type": "reference",
            "x-reference-model": field.comodel_name,
        }

    def _handle_vocabulary(self, field) -> dict[str, Any]:
        domain_str = str(field.domain) if field.domain else ""
        vocab_info = self._extract_vocabulary_info_from_domain(
            domain_str,
            field.comodel_name,
        )

        prop: dict[str, Any] = {
            "type": "object",
            "properties": {
                "system": {"type": "string"},
                "code": {"type": "string"},
            },
            "required": ["system", "code"],
            "x-field-type": "vocabulary",
        }

        if vocab_info:
            namespace_uri = vocab_info["namespaceUri"]
            prop["properties"]["system"] = {"type": "string", "const": namespace_uri}
            prop["x-vocabulary-uri"] = namespace_uri

            codes = vocab_info["codes"]
            if codes:
                prop["properties"]["code"] = {
                    "oneOf": [{"const": c["value"], "title": c["label"]} for c in codes],
                }

        return prop

    # ------------------------------------------------------------------
    # Helpers (selection & vocabulary extraction)
    # ------------------------------------------------------------------

    def _extract_selection_choices(self, field) -> list[dict[str, str]]:
        """Extract selection choices from an Odoo field.

        Handles both list-of-tuples and callable selections.
        """
        selection = field.selection
        if callable(selection):
            try:
                selection = selection(self.env[field.model_name])
            except Exception:
                _logger.warning("Could not evaluate callable selection for %s", field.name, exc_info=True)
                return []
        if not selection:
            return []
        result = []
        for item in selection:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result.append({"value": item[0], "label": item[1]})
            else:
                _logger.debug("Skipping unparseable selection item for %s: %r", field.name, item)
        return result

    def _extract_vocabulary_info_from_domain(
        self,
        domain_str: str,
        comodel_name: str,
    ) -> dict[str, Any] | None:
        """Parse a domain string to extract vocabulary namespace and load codes.

        Args:
            domain_str: String representation of an Odoo domain (e.g.
                ``[('namespace_uri', '=', 'urn:iso:std:iso:5218')]``)
            comodel_name: The comodel (expected to be ``spp.vocabulary.code``)

        Returns:
            Dict with ``namespaceUri`` and ``codes``, or None if unparseable.
        """
        if not domain_str:
            return None

        try:
            domain = ast.literal_eval(domain_str)
        except (ValueError, SyntaxError):
            # Domain contains Python name references (e.g., registrant_id)
            return None

        if not isinstance(domain, list):
            return None

        namespace_uri = None
        for leaf in domain:
            if not isinstance(leaf, (list, tuple)) or len(leaf) != 3:
                continue
            field_path, operator, value = leaf
            if operator != "=":
                continue
            if field_path in ("namespace_uri", "vocabulary_id.namespace_uri"):
                namespace_uri = value
                break

        if not namespace_uri:
            return None

        codes = self.env[comodel_name].search(
            [("namespace_uri", "=", namespace_uri)],
            order="sequence, code",
        )
        return {
            "namespaceUri": namespace_uri,
            "codes": [{"value": code.code, "label": code.display or code.code} for code in codes],
        }

    # ------------------------------------------------------------------
    # Dispatch table (Odoo field type string → handler method)
    # ------------------------------------------------------------------

    _TYPE_HANDLERS: dict[str, Any] = {
        "char": _handle_char,
        "text": _handle_text,
        "html": _handle_text,
        "integer": _handle_integer,
        "float": _handle_float,
        "monetary": _handle_float,
        "boolean": _handle_boolean,
        "date": _handle_date,
        "datetime": _handle_datetime,
        "selection": _handle_selection,
    }
