# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Studio Logic Validation Tests.

This module validates all variables and logic packs from spp_studio
to ensure they compile and work correctly. It checks:

- Variable CEL accessors parse correctly
- Computed variables compile
- Aggregate variables build valid CEL
- Logic pack items have valid JSON and CEL expressions
- Published logic expressions are valid
- Variable references are consistent

These tests help catch configuration errors early and ensure studio
logic is production-ready.
"""

import json
import logging
import time

from odoo.tests import tagged

from odoo.addons.spp_cel_domain.services.cel_parser import parse

from .common import PerformanceTestCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "studio_validation")
class TestStudioVariableValidation(PerformanceTestCase):
    """Validation tests for spp.cel.variable records."""

    @classmethod
    def setUpClass(cls):
        """Initialize test environment."""
        super().setUpClass()
        if "spp.cel.variable" not in cls.env:
            cls._module_installed = False
            return
        cls._module_installed = True

    def test_all_variables_have_cel_accessor(self):
        """Verify all active variables have a non-empty cel_accessor."""
        if not self._module_installed:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        variables = self.env["spp.cel.variable"].search([("active", "=", True)])
        missing = []

        for var in variables:
            if not var.cel_accessor:
                missing.append(
                    {
                        "id": var.id,
                        "name": var.name,
                        "source_type": var.source_type,
                    }
                )

        elapsed = time.perf_counter() - start_time

        if missing:
            _logger.warning("Variables missing cel_accessor:")
            for miss in missing:
                _logger.warning(
                    "  - ID %s: %s (type: %s)",
                    miss["id"],
                    miss["name"],
                    miss["source_type"],
                )

        _logger.info(
            "Checked %d variables for cel_accessor in %.3fs",
            len(variables),
            elapsed,
        )

        self.assertEqual(
            len(missing),
            0,
            f"{len(missing)} variables are missing cel_accessor",
        )

    def test_all_cel_accessors_parse(self):
        """Validate all variable CEL accessors can be parsed."""
        if not self._module_installed:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        variables = self.env["spp.cel.variable"].search([("active", "=", True)])
        errors = []

        for var in variables:
            if not var.cel_accessor:
                continue
            try:
                parse(var.cel_accessor)
            except Exception as e:
                errors.append(
                    {
                        "id": var.id,
                        "name": var.name,
                        "accessor": var.cel_accessor,
                        "error": str(e),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Variables with invalid CEL accessors:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s): %s -> %s",
                    err["name"],
                    err["id"],
                    err["accessor"],
                    err["error"],
                )

        _logger.info(
            "Parsed %d variable accessors in %.3fs (%d errors)",
            len(variables),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} variables have invalid CEL accessors",
        )

    def test_computed_variables_compile(self):
        """Verify computed variables have valid cel_expression."""
        if not self._module_installed:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        variables = self.env["spp.cel.variable"].search(
            [
                ("active", "=", True),
                ("source_type", "=", "computed"),
            ]
        )
        errors = []

        for var in variables:
            if not var.cel_expression:
                errors.append(
                    {
                        "id": var.id,
                        "name": var.name,
                        "error": "Missing cel_expression",
                    }
                )
                continue

            try:
                parse(var.cel_expression)
            except Exception as e:
                errors.append(
                    {
                        "id": var.id,
                        "name": var.name,
                        "expression": var.cel_expression,
                        "error": str(e),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Computed variables with invalid expressions:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s): %s -> %s",
                    err["name"],
                    err["id"],
                    err.get("expression", "N/A"),
                    err["error"],
                )

        _logger.info(
            "Validated %d computed variables in %.3fs (%d errors)",
            len(variables),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} computed variables have invalid expressions",
        )

    def test_aggregate_variables_build_cel(self):
        """Verify aggregate variables build valid CEL expressions."""
        if not self._module_installed:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        variables = self.env["spp.cel.variable"].search(
            [
                ("active", "=", True),
                ("source_type", "=", "aggregate"),
            ]
        )
        errors = []

        for var in variables:
            try:
                # Call the method to build aggregate CEL
                cel_expr = var._build_aggregate_cel()

                # Try to parse the generated expression
                if cel_expr and cel_expr != var.cel_accessor:
                    parse(cel_expr)
            except Exception as e:
                errors.append(
                    {
                        "id": var.id,
                        "name": var.name,
                        "aggregate_type": var.aggregate_type,
                        "error": str(e),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Aggregate variables with build errors:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s, type: %s): %s",
                    err["name"],
                    err["id"],
                    err["aggregate_type"],
                    err["error"],
                )

        _logger.info(
            "Validated %d aggregate variables in %.3fs (%d errors)",
            len(variables),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} aggregate variables have build errors",
        )

    def test_variable_categories_exist(self):
        """Verify all referenced category_ids exist and are accessible."""
        if not self._module_installed:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        variables = self.env["spp.cel.variable"].search(
            [
                ("active", "=", True),
                ("category_id", "!=", False),
            ]
        )
        orphaned = []

        for var in variables:
            if var.category_id:
                try:
                    # Try to access the category
                    _ = var.category_id.name
                except Exception as e:
                    orphaned.append(
                        {
                            "id": var.id,
                            "name": var.name,
                            "category_id": var.category_id.id if var.category_id else None,
                            "error": str(e),
                        }
                    )

        elapsed = time.perf_counter() - start_time

        if orphaned:
            _logger.warning("Variables with orphaned category references:")
            for orp in orphaned:
                _logger.warning(
                    "  - %s (ID %s): category_id=%s -> %s",
                    orp["name"],
                    orp["id"],
                    orp["category_id"],
                    orp["error"],
                )

        _logger.info(
            "Checked %d variable categories in %.3fs (%d orphaned)",
            len(variables),
            elapsed,
            len(orphaned),
        )

        self.assertEqual(
            len(orphaned),
            0,
            f"{len(orphaned)} variables have orphaned category references",
        )


@tagged("post_install", "-at_install", "studio_validation")
class TestStudioLogicPackValidation(PerformanceTestCase):
    """Validation tests for spp.studio.pack and spp.studio.pack.item records."""

    @classmethod
    def setUpClass(cls):
        """Initialize test environment."""
        super().setUpClass()
        if "spp.studio.pack" not in cls.env:
            cls._module_installed = False
            return
        cls._module_installed = True

    def test_all_packs_have_items(self):
        """Verify all packs have at least one item."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        packs = self.env["spp.studio.pack"].search([])
        empty = []

        for pack in packs:
            if not pack.item_ids:
                empty.append(
                    {
                        "id": pack.id,
                        "name": pack.name,
                        "code": pack.code,
                    }
                )

        elapsed = time.perf_counter() - start_time

        if empty:
            _logger.warning("Empty packs (no items):")
            for emp in empty:
                _logger.warning(
                    "  - %s (ID %s, code: %s)",
                    emp["name"],
                    emp["id"],
                    emp["code"],
                )

        _logger.info(
            "Checked %d packs for items in %.3fs (%d empty)",
            len(packs),
            elapsed,
            len(empty),
        )

        self.assertEqual(
            len(empty),
            0,
            f"{len(empty)} packs have no items",
        )

    def test_all_pack_items_have_valid_json(self):
        """Verify all pack items have valid JSON in logic_data.

        OpenSPP2 contract (see spp_studio pack_install_wizard): logic_data
        is a JSON object whose 'cel_expression' key holds the CEL source
        installed into spp.cel.expression. There is no 'mode' key.
        """
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        items = self.env["spp.studio.pack.item"].search([])
        errors = []

        for item in items:
            if not item.logic_data:
                errors.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "pack": item.pack_id.name if item.pack_id else "N/A",
                        "error": "Missing logic_data",
                    }
                )
                continue

            try:
                data = json.loads(item.logic_data)

                cel_expr = data.get("cel_expression")
                if not cel_expr or not isinstance(cel_expr, str):
                    errors.append(
                        {
                            "id": item.id,
                            "name": item.name,
                            "pack": item.pack_id.name if item.pack_id else "N/A",
                            "error": "Missing or empty 'cel_expression' in JSON",
                        }
                    )

            except json.JSONDecodeError as e:
                errors.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "pack": item.pack_id.name if item.pack_id else "N/A",
                        "error": f"Invalid JSON: {str(e)}",
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Pack items with invalid JSON:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s, pack: %s): %s",
                    err["name"],
                    err["id"],
                    err["pack"],
                    err["error"],
                )

        _logger.info(
            "Validated JSON for %d pack items in %.3fs (%d errors)",
            len(items),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} pack items have invalid JSON",
        )

    def test_all_pack_cel_expressions_parse(self):
        """Verify CEL expressions in pack items parse correctly."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        items = self.env["spp.studio.pack.item"].search([])
        errors = []

        for item in items:
            data = {}
            try:
                data = item.get_logic_dict()
                cel_expr = data.get("cel_expression")
                if cel_expr:
                    parse(cel_expr)
            except json.JSONDecodeError:
                # JSON errors are caught in previous test
                pass
            except Exception as e:
                errors.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "pack": item.pack_id.name if item.pack_id else "N/A",
                        "expression": data.get("cel_expression", "N/A"),
                        "error": str(e),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Pack items with unparseable CEL expressions:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s, pack: %s)",
                    err["name"],
                    err["id"],
                    err["pack"],
                )
                _logger.warning("    Expression: %s", err["expression"][:100])
                _logger.warning("    Error: %s", err["error"])

        _logger.info(
            "Parsed CEL in %d pack items in %.3fs (%d errors)",
            len(items),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} pack items have unparseable CEL expressions",
        )

    def test_all_pack_cel_expressions_translate(self):
        """Verify CEL expressions can be translated to Python."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        # Check if translator is available
        if "spp.cel.translator" not in self.env:
            self.skipTest("spp_cel_domain not installed")

        start_time = time.perf_counter()
        translator = self.env["spp.cel.translator"]
        resolver = self.env["spp.cel.variable.resolver"]
        # Use the standard registry_individuals profile for translation,
        # consistent with other CEL performance tests.
        cfg = self.cel_registry.load_profile("registry_individuals")
        model = cfg.get("root_model", "res.partner")
        items = self.env["spp.studio.pack.item"].search([])
        errors = []
        translated_count = 0
        unresolved_count = 0

        for item in items:
            data = {}
            resolved_expr = "N/A"
            try:
                data = item.get_logic_dict()
                cel_expr = data.get("cel_expression")
                if cel_expr:
                    # Pack expressions reference studio variables; expand
                    # them the same way installation does before translating.
                    resolution = resolver.preview_resolution(cel_expr, context_type="individual")
                    if resolution.get("missing_variables"):
                        # Variable availability is asserted separately by
                        # test_pack_required_variables_exist
                        unresolved_count += 1
                        continue
                    resolved_expr = resolution.get("expression") or cel_expr
                    translator.translate(model, resolved_expr, cfg)
                    translated_count += 1
            except json.JSONDecodeError:
                # JSON errors are caught in previous test
                pass
            except Exception as e:
                errors.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "pack": item.pack_id.name if item.pack_id else "N/A",
                        "expression": resolved_expr,
                        "error": str(e),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Pack items with translation errors:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s, pack: %s)",
                    err["name"],
                    err["id"],
                    err["pack"],
                )
                _logger.warning("    Expression: %s", err["expression"][:100])
                _logger.warning("    Error: %s", err["error"])

        _logger.info(
            "Translated %d/%d CEL expressions in %.3fs (%d errors, %d with unresolved variables)",
            translated_count,
            len(items),
            elapsed,
            len(errors),
            unresolved_count,
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} pack items have translation errors",
        )

    def test_pack_required_variables_exist(self):
        """Verify all required variables referenced by packs exist."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        packs = self.env["spp.studio.pack"].search(
            [
                ("required_variable_ids", "!=", False),
            ]
        )
        Variable = self.env["spp.cel.variable"]
        missing = []

        for pack in packs:
            for var in pack.required_variable_ids:
                # Check if variable exists and is active
                exists = Variable.search(
                    [
                        ("name", "=", var.name),
                        ("active", "=", True),
                    ],
                    limit=1,
                )

                if not exists:
                    missing.append(
                        {
                            "pack_id": pack.id,
                            "pack_name": pack.name,
                            "variable_id": var.id,
                            "variable_name": var.name,
                        }
                    )

        elapsed = time.perf_counter() - start_time

        if missing:
            _logger.warning("Packs with missing required variables:")
            for miss in missing:
                _logger.warning(
                    "  - Pack '%s' (ID %s) requires variable '%s' (ID %s)",
                    miss["pack_name"],
                    miss["pack_id"],
                    miss["variable_name"],
                    miss["variable_id"],
                )

        _logger.info(
            "Checked required variables for %d packs in %.3fs (%d missing)",
            len(packs),
            elapsed,
            len(missing),
        )

        self.assertEqual(
            len(missing),
            0,
            f"{len(missing)} required variable dependencies are missing",
        )

    def test_no_legacy_logic_data_schema(self):
        """Verify no pack item still carries the legacy logic_data schema.

        The pre-OpenSPP2 studio stored logic_data as {'mode': 'simple'|
        'advanced', 'conditions': [...], ...}. OpenSPP2 consumes only
        'cel_expression' (plus optional metadata); a 'mode' or 'conditions'
        key indicates data that installation would silently ignore.
        """
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        items = self.env["spp.studio.pack.item"].search([])
        legacy = []

        for item in items:
            try:
                data = item.get_logic_dict()
            except json.JSONDecodeError:
                # JSON errors are caught in test_all_pack_items_have_valid_json
                continue

            legacy_keys = {"mode", "conditions"} & set(data)
            if legacy_keys:
                legacy.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "pack": item.pack_id.name if item.pack_id else "N/A",
                        "keys": sorted(legacy_keys),
                    }
                )

        elapsed = time.perf_counter() - start_time

        if legacy:
            _logger.warning("Pack items with legacy logic_data keys:")
            for leg in legacy:
                _logger.warning(
                    "  - %s (ID %s, pack: %s): %s",
                    leg["name"],
                    leg["id"],
                    leg["pack"],
                    leg["keys"],
                )

        _logger.info(
            "Checked %d pack items for legacy schema in %.3fs (%d legacy)",
            len(items),
            elapsed,
            len(legacy),
        )

        self.assertEqual(
            len(legacy),
            0,
            f"{len(legacy)} pack items still use the legacy logic_data schema",
        )


@tagged("post_install", "-at_install", "studio_validation")
class TestStudioLogicValidation(PerformanceTestCase):
    """Validation tests for installed spp.cel.expression records."""

    @classmethod
    def setUpClass(cls):
        """Initialize test environment."""
        super().setUpClass()
        if "spp.cel.expression" not in cls.env:
            cls._module_installed = False
            return
        # Check if spp_studio is installed by verifying published_expression field exists
        if "published_expression" not in cls.env["spp.cel.expression"]._fields:
            cls._module_installed = False
            return
        cls._module_installed = True

    def test_all_published_logic_expressions_valid(self):
        """Verify all published logic records have valid expressions."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        logic_records = self.env["spp.cel.expression"].search(
            [
                ("state", "=", "published"),
            ]
        )
        errors = []

        for logic in logic_records:
            # Check published_expression
            if logic.published_expression:
                try:
                    parse(logic.published_expression)
                except Exception as e:
                    errors.append(
                        {
                            "id": logic.id,
                            "name": logic.name,
                            "code": logic.code,
                            "field": "published_expression",
                            "expression": logic.published_expression,
                            "error": str(e),
                        }
                    )

        elapsed = time.perf_counter() - start_time

        if errors:
            _logger.warning("Published logic with invalid expressions:")
            for err in errors:
                _logger.warning(
                    "  - %s (ID %s, code: %s) [%s]",
                    err["name"],
                    err["id"],
                    err["code"],
                    err["field"],
                )
                _logger.warning("    Expression: %s", err["expression"][:100])
                _logger.warning("    Error: %s", err["error"])

        _logger.info(
            "Validated %d published logic records in %.3fs (%d errors)",
            len(logic_records),
            elapsed,
            len(errors),
        )

        self.assertEqual(
            len(errors),
            0,
            f"{len(errors)} published logic records have invalid expressions",
        )

    def test_logic_variable_references_valid(self):
        """Verify referenced variables exist for all logic records."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        logic_records = self.env["spp.cel.expression"].search([])
        missing = []

        for logic in logic_records:
            if logic.variable_ids:
                for var in logic.variable_ids:
                    # Check if variable still exists and is accessible
                    try:
                        _ = var.name
                        _ = var.cel_accessor
                    except Exception as e:
                        missing.append(
                            {
                                "logic_id": logic.id,
                                "logic_name": logic.name,
                                "variable_id": var.id,
                                "error": str(e),
                            }
                        )

        elapsed = time.perf_counter() - start_time

        if missing:
            _logger.warning("Logic records with inaccessible variable references:")
            for miss in missing:
                _logger.warning(
                    "  - Logic '%s' (ID %s) references variable ID %s: %s",
                    miss["logic_name"],
                    miss["logic_id"],
                    miss["variable_id"],
                    miss["error"],
                )

        _logger.info(
            "Validated variable references for %d logic records in %.3fs (%d errors)",
            len(logic_records),
            elapsed,
            len(missing),
        )

        self.assertEqual(
            len(missing),
            0,
            f"{len(missing)} logic records have invalid variable references",
        )

    def test_logic_output_types_consistent(self):
        """Verify output_type matches expression result type (basic check)."""
        if not self._module_installed:
            self.skipTest("spp_studio not installed")

        start_time = time.perf_counter()
        logic_records = self.env["spp.cel.expression"].search(
            [
                ("published_expression", "!=", False),
            ]
        )
        warnings = []

        for logic in logic_records:
            expr = logic.published_expression
            output_type = logic.output_type

            # Basic heuristic checks (not comprehensive)
            try:
                # Boolean expressions often contain comparisons
                has_comparison = any(op in expr for op in ["==", "!=", "<", ">", "<=", ">=", "&&", "||"])
                has_boolean_keyword = any(kw in expr.lower() for kw in ["true", "false"])

                if output_type == "boolean" and not (has_comparison or has_boolean_keyword):
                    # May not be boolean - this is just a warning
                    warnings.append(
                        {
                            "id": logic.id,
                            "name": logic.name,
                            "output_type": output_type,
                            "expression": expr[:100],
                            "issue": "Boolean output but no comparison operators found",
                        }
                    )

                # Number/money expressions might start with calculations
                if output_type in ("number", "money"):
                    # Just log for now - hard to validate without actual execution
                    pass

            except Exception as e:
                _logger.debug("Error checking output type for logic %s: %s", logic.name, e)

        elapsed = time.perf_counter() - start_time

        if warnings:
            _logger.info("Logic records with potential output type mismatches:")
            for warn in warnings:
                _logger.info(
                    "  - %s (ID %s): %s",
                    warn["name"],
                    warn["id"],
                    warn["issue"],
                )

        _logger.info(
            "Checked output types for %d logic records in %.3fs (%d warnings)",
            len(logic_records),
            elapsed,
            len(warnings),
        )

        # This test only warns - don't fail
        # Output type validation is complex and may have false positives
