"""
CEL Vocabulary Translator - Domain Translation Extension.

Extends the CEL translator to handle vocabulary-aware functions and translate
them into Odoo domains that check code URIs and reference URIs.

ADR-016 Phase 3: CEL Integration for vocabulary-aware expressions.
"""

import logging
from typing import Any

from odoo import models

from odoo.addons.spp_cel_domain.models.cel_queryplan import LeafDomain
from odoo.addons.spp_cel_domain.services import cel_parser as P

_logger = logging.getLogger(__name__)


class CelVocabularyTranslator(models.AbstractModel):
    """Extends CEL translator to handle vocabulary functions.

    This model adds domain translation support for vocabulary-aware
    CEL functions like in_group(), code(), and code_eq().
    """

    _inherit = "spp.cel.translator"

    # Semantic helper functions mapped to concept groups
    SEMANTIC_HELPERS = {
        "is_female": "feminine_gender",
        "is_male": "masculine_gender",
        "is_head": "head_of_household",
        "is_pregnant": "pregnant_eligible",
    }

    def _to_plan(self, model: str, node: Any, cfg: dict[str, Any], ctx: dict[str, Any]):  # noqa: C901
        """Extended to handle vocabulary-aware function calls.

        Adds support for:
        - in_group(field, "group_name") → domain checking code URIs
        - code_eq(field, "identifier") → domain checking with reference_uri
        - code("identifier") → resolved code for comparisons
        - is_female(field), is_male(field), etc. → semantic helper shortcuts
        """
        # Handle vocabulary function calls - don't catch exceptions, let them propagate
        if isinstance(node, P.Call) and isinstance(node.func, P.Ident):
            func_name = node.func.name

            # Handle in_group(field, group_name)
            if func_name == "in_group" and len(node.args) >= 2:
                return self._handle_in_group(model, node, cfg, ctx)

            # Handle code_eq(field, identifier)
            if func_name == "code_eq" and len(node.args) >= 2:
                return self._handle_code_eq(model, node, cfg, ctx)

            # Handle semantic helpers: is_female(field), is_male(field), etc.
            if func_name in self.SEMANTIC_HELPERS and len(node.args) >= 1:
                _logger.debug("[CEL Vocabulary] Handling semantic helper %s for model %s", func_name, model)
                return self._handle_semantic_helper(model, node, cfg, ctx, func_name)

        # Handle comparisons with code() calls
        if isinstance(node, P.Compare):
            # Check if either side is a code() call
            if isinstance(node.left, P.Call) and isinstance(node.left.func, P.Ident) and node.left.func.name == "code":
                return self._handle_code_comparison(model, node, cfg, ctx, left_is_code=True)

            if (
                isinstance(node.right, P.Call)
                and isinstance(node.right.func, P.Ident)
                and node.right.func.name == "code"
            ):
                return self._handle_code_comparison(model, node, cfg, ctx, left_is_code=False)

        # Fall back to parent implementation
        return super()._to_plan(model, node, cfg, ctx)

    def _handle_in_group(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Translate in_group(field, group_name) to domain.

        Args:
            model: Current model name
            node: AST Call node
            cfg: Configuration dictionary
            ctx: Context dictionary

        Returns:
            tuple: (plan, explain) for the in_group check

        Example:
            in_group(r.gender_id, "feminine_gender")
            → ["|",
                ("gender_id.uri", "in", ["urn:iso:std:iso:5218#2", ...]),
                ("gender_id.reference_uri", "in", ["urn:iso:std:iso:5218#2", ...])
               ]
        """
        # Resolve the field being checked
        field_node = node.args[0]
        try:
            field_name, field_model = self._resolve_field(model, field_node, cfg, ctx)
            field_name = self._normalize_field_name(field_model or model, field_name)
        except Exception as e:
            _logger.warning(
                "[CEL Vocabulary] Failed to resolve field in in_group(): %s. "
                "Check that the field name matches the Odoo model field (e.g., gender_id, not gender).",
                e,
            )
            return (
                LeafDomain(model, [("id", "=", 0)]),
                "in_group() [FIELD RESOLUTION ERROR]",
            )

        # Get the group name
        try:
            group_name = self._eval_literal(node.args[1], ctx)
        except Exception as e:
            _logger.warning("[CEL Vocabulary] Failed to evaluate group name in in_group(): %s", e)
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"in_group({field_name}, ?) [EVAL ERROR]",
            )

        if not group_name:
            _logger.warning("[CEL Vocabulary] Empty group name in in_group() call")
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"in_group({field_name}, EMPTY) [INVALID GROUP]",
            )

        # Look up the concept group
        group = self.env["spp.vocabulary.concept.group"].search([("name", "=", group_name)], limit=1)

        if not group:
            _logger.warning(
                "[CEL Vocabulary] Concept group '%s' not found. "
                "Check Settings > Vocabularies > Concept Groups.",
                group_name,
            )
            # Return domain that matches nothing
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"in_group({field_name}, '{group_name}') [GROUP NOT FOUND]",
            )

        # Get all URIs in the group (includes reference_uri mappings)
        uri_list = group.get_code_uris()

        if not uri_list:
            _logger.warning(
                "[CEL Vocabulary] Concept group '%s' has no codes. "
                "Add codes via Settings > Vocabularies > Concept Groups.",
                group_name,
            )
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"in_group({field_name}, '{group_name}') [EMPTY GROUP]",
            )

        # Build domain: field.uri IN uris OR field.reference_uri IN uris
        domain = [
            "|",
            (f"{field_name}.uri", "in", uri_list),
            (f"{field_name}.reference_uri", "in", uri_list),
        ]

        explain = f"{field_name} IN GROUP '{group_name}' ({len(uri_list)} codes)"

        return LeafDomain(field_model or model, domain), explain

    def _handle_semantic_helper(
        self,
        model: str,
        node: P.Call,
        cfg: dict[str, Any],
        ctx: dict[str, Any],
        func_name: str,
    ):
        """Translate semantic helper functions like is_female(field) to domain.

        Semantic helpers are shortcuts for in_group() calls:
        - is_female(field) → in_group(field, "feminine_gender")
        - is_male(field) → in_group(field, "masculine_gender")
        - is_head(field) → in_group(field, "head_of_household")
        - etc.

        Args:
            model: Current model name
            node: AST Call node
            cfg: Configuration dictionary
            ctx: Context dictionary
            func_name: Name of the semantic helper function

        Returns:
            tuple: (plan, explain) for the group check
        """
        group_name = self.SEMANTIC_HELPERS.get(func_name)
        if not group_name:
            _logger.warning("[CEL Vocabulary] Unknown semantic helper: %s", func_name)
            return (
                LeafDomain(model, [("id", "=", 0)]),
                f"{func_name}() [UNKNOWN HELPER]",
            )

        # Resolve the field being checked
        field_node = node.args[0]
        try:
            field_name, field_model = self._resolve_field(model, field_node, cfg, ctx)
            field_name = self._normalize_field_name(field_model or model, field_name)
        except Exception as e:
            _logger.warning(
                "[CEL Vocabulary] Failed to resolve field in %s(): %s. "
                "Check that the field name matches the Odoo model field (e.g., gender_id, not gender).",
                func_name,
                e,
            )
            return (
                LeafDomain(model, [("id", "=", 0)]),
                f"{func_name}() [FIELD RESOLUTION ERROR]",
            )

        # Look up the concept group
        group = self.env["spp.vocabulary.concept.group"].search([("name", "=", group_name)], limit=1)

        if not group:
            _logger.warning(
                "[CEL Vocabulary] Concept group '%s' not found for %s(). "
                "Check Settings > Vocabularies > Concept Groups.",
                group_name,
                func_name,
            )
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"{func_name}({field_name}) [GROUP '{group_name}' NOT FOUND]",
            )

        # Get all URIs in the group
        uri_list = group.get_code_uris()

        if not uri_list:
            _logger.warning(
                "[CEL Vocabulary] Concept group '%s' has no codes for %s(). "
                "Add codes via Settings > Vocabularies > Concept Groups.",
                group_name,
                func_name,
            )
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"{func_name}({field_name}) [GROUP EMPTY]",
            )

        # Build domain: field.uri IN uris OR field.reference_uri IN uris
        domain = [
            "|",
            (f"{field_name}.uri", "in", uri_list),
            (f"{field_name}.reference_uri", "in", uri_list),
        ]

        explain = f"{func_name}({field_name}) → '{group_name}' ({len(uri_list)} codes)"

        return LeafDomain(field_model or model, domain), explain

    def _handle_code_eq(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Translate code_eq(field, identifier) to domain.

        Args:
            model: Current model name
            node: AST Call node
            cfg: Configuration dictionary
            ctx: Context dictionary

        Returns:
            tuple: (plan, explain) for the code_eq check

        Example:
            code_eq(r.gender_id, "female")
            → ["|",
                ("gender_id.uri", "=", "urn:iso:std:iso:5218#2"),
                ("gender_id.reference_uri", "=", "urn:iso:std:iso:5218#2")
               ]
        """
        # Resolve the field being checked
        field_node = node.args[0]
        try:
            field_name, field_model = self._resolve_field(model, field_node, cfg, ctx)
            field_name = self._normalize_field_name(field_model or model, field_name)
        except Exception as e:
            _logger.warning(
                "[CEL Vocabulary] Failed to resolve field in code_eq(): %s. "
                "Check that the field name matches the Odoo model field (e.g., gender_id, not gender).",
                e,
            )
            return (
                LeafDomain(model, [("id", "=", 0)]),
                "code_eq() [FIELD RESOLUTION ERROR]",
            )

        # Get the identifier to compare against
        try:
            identifier = self._eval_literal(node.args[1], ctx)
        except Exception as e:
            _logger.warning("[CEL Vocabulary] Failed to evaluate identifier in code_eq(): %s", e)
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"code_eq({field_name}, ?) [EVAL ERROR]",
            )

        # Resolve the target code
        if isinstance(identifier, str) and identifier.startswith("urn:"):
            # Direct URI
            target_code = self.env["spp.vocabulary.code"].resolve_by_uri(identifier)
        else:
            # Alias resolution
            target_code = self.env["spp.vocabulary.code"].resolve_alias(identifier)

        if not target_code:
            _logger.warning(
                "[CEL Vocabulary] Could not resolve code identifier '%s'. "
                "Verify the vocabulary code exists (check by URI, code value, or display name).",
                identifier,
            )
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"code_eq({field_name}, '{identifier}') [CODE NOT FOUND]",
            )

        # Build domain: field.uri = target.uri OR field.reference_uri = target.uri
        domain = [
            "|",
            (f"{field_name}.uri", "=", target_code.uri),
            (f"{field_name}.reference_uri", "=", target_code.uri),
        ]

        explain = f"code_eq({field_name}, '{identifier}') → {target_code.uri}"

        return LeafDomain(field_model or model, domain), explain

    def _handle_code_comparison(
        self,
        model: str,
        node: P.Compare,
        cfg: dict[str, Any],
        ctx: dict[str, Any],
        left_is_code: bool,
    ):
        """Handle comparisons involving code() function calls.

        Args:
            model: Current model name
            node: AST Compare node
            cfg: Configuration dictionary
            ctx: Context dictionary
            left_is_code: True if left side is code(), False if right side is

        Returns:
            tuple: (plan, explain) for the comparison

        Example:
            r.gender_id == code("female")
            → ["|",
                ("gender_id.uri", "=", "urn:iso:std:iso:5218#2"),
                ("gender_id.reference_uri", "=", "urn:iso:std:iso:5218#2")
               ]
        """
        opmap = {"EQ": "=", "NE": "!=", "GT": ">", "GE": ">=", "LT": "<", "LE": "<="}

        if left_is_code:
            # code() on left, field on right (unusual but support it)
            code_node = node.left
            field_node = node.right
            # Swap comparison operator for reversed order
            op = opmap.get(node.op, "=")
        else:
            # field on left, code() on right (normal case)
            field_node = node.left
            code_node = node.right
            op = opmap.get(node.op, "=")

        # Only support equality/inequality for code comparisons
        if op not in ("=", "!="):
            _logger.warning("[CEL Vocabulary] code() comparisons only support == and !=, got %s", node.op)
            return super()._to_plan(model, node, cfg, ctx)

        # Resolve the field
        try:
            field_name, field_model = self._resolve_field(model, field_node, cfg, ctx)
            field_name = self._normalize_field_name(field_model or model, field_name)
        except Exception as e:
            _logger.warning(
                "[CEL Vocabulary] Failed to resolve field in code comparison: %s. "
                "Check that the field name matches the Odoo model field (e.g., gender_id, not gender).",
                e,
            )
            return (
                LeafDomain(model, [("id", "=", 0)]),
                "code() comparison [FIELD RESOLUTION ERROR]",
            )

        # Resolve the code identifier
        try:
            identifier = self._eval_literal(code_node.args[0], ctx) if code_node.args else None
        except Exception as e:
            _logger.warning("[CEL Vocabulary] Failed to evaluate code identifier: %s", e)
            identifier = None

        if not identifier:
            _logger.warning("[CEL Vocabulary] Empty identifier in code() call")
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"{field_name} {op} code(EMPTY)",
            )

        # Resolve the target code
        if isinstance(identifier, str) and identifier.startswith("urn:"):
            target_code = self.env["spp.vocabulary.code"].resolve_by_uri(identifier)
        else:
            target_code = self.env["spp.vocabulary.code"].resolve_alias(identifier)

        if not target_code:
            _logger.warning(
                "[CEL Vocabulary] Could not resolve code '%s'. "
                "Verify the vocabulary code exists (check by URI, code value, or display name).",
                identifier,
            )
            return (
                LeafDomain(field_model or model, [("id", "=", 0)]),
                f"{field_name} {op} code('{identifier}') [NOT FOUND]",
            )

        # Build domain
        if op == "=":
            # field.uri = target.uri OR field.reference_uri = target.uri
            domain = [
                "|",
                (f"{field_name}.uri", "=", target_code.uri),
                (f"{field_name}.reference_uri", "=", target_code.uri),
            ]
        else:  # op == "!="
            # NOT (field.uri = target.uri OR field.reference_uri = target.uri)
            # Which is: field.uri != target.uri AND field.reference_uri != target.uri
            domain = [
                "&",
                (f"{field_name}.uri", "!=", target_code.uri),
                (f"{field_name}.reference_uri", "!=", target_code.uri),
            ]

        explain = f"{field_name} {op} code('{identifier}') → {target_code.uri}"

        return LeafDomain(field_model or model, domain), explain
