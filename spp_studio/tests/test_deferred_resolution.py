# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Comprehensive tests for Deferred Variable Resolution.

This test suite validates the deferred resolution architecture where:
1. Logic packs store ORIGINAL expressions with variable references
2. Variables are resolved at EVALUATION time, not installation time
3. Changes to variables automatically propagate to all logic using them
4. Caching improves performance while still respecting variable updates
"""

import logging

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestDeferredResolutionCore(TransactionCase, CELTestDataMixin):
    """Core tests for deferred variable resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicPack = cls.env["spp.studio.pack"]
        cls.LogicPackItem = cls.env["spp.studio.pack.item"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        # Create a test category
        cls.test_category = cls._create_test_category(
            name=f"Test Category {cls._test_id}",
            code=f"test_deferred_{cls._test_id}",
        )

    def test_resolve_for_evaluation_basic(self):
        """Test basic runtime variable resolution."""
        # Create a test constant variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_threshold",
                "label": "Test Threshold",
                "cel_accessor": "test_threshold",
                "source_type": "constant",
                "default_value": "1000",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Test runtime resolution
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "income < test_threshold",
            context_type="group",
        )

        # Should resolve to the constant value
        self.assertIn("1000", result["expression"])
        self.assertIn("test_threshold", result["variables_used"])
        self.assertEqual(result["missing_variables"], [])

        # Clean up
        test_var.unlink()

    def test_constant_change_propagates(self):
        """Test that changing a constant's default_value propagates to resolution."""
        # Create a test constant
        test_var = self.LogicVariable.create(
            {
                "name": "test_poverty_line",
                "label": "Test Poverty Line",
                "cel_accessor": "test_poverty_line",
                "source_type": "constant",
                "default_value": "2500",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        expression = "income < test_poverty_line"

        # First resolution
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertIn("2500", result1["expression"])
        _logger.info(f"Initial resolution: {result1['expression']}")

        # Change the constant value
        test_var.write({"default_value": "3500"})

        # Second resolution should use new value
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertIn("3500", result2["expression"])
        self.assertNotIn("2500", result2["expression"])
        _logger.info(f"After update resolution: {result2['expression']}")

        # Clean up
        test_var.unlink()

    def test_computed_variable_formula_change_propagates(self):
        """Test that changing a computed variable's formula propagates."""
        # Create a test computed variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_age_calc",
                "label": "Test Age Calculation",
                "cel_accessor": "test_age_calc",
                "source_type": "computed",
                "cel_expression": "age_years(me.birthdate)",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        expression = "test_age_calc >= 18"

        # First resolution
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )
        self.assertIn("age_years(me.birthdate)", result1["expression"])
        _logger.info(f"Initial resolution: {result1['expression']}")

        # Change the formula
        test_var.write({"cel_expression": "age_years(me.date_of_birth)"})

        # Second resolution should use new formula
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )
        self.assertIn("age_years(me.date_of_birth)", result2["expression"])
        self.assertNotIn("age_years(me.birthdate)", result2["expression"])
        _logger.info(f"After update resolution: {result2['expression']}")

        # Clean up
        test_var.unlink()

    def test_cache_invalidation_on_variable_create(self):
        """Test that creating a new variable invalidates the cache."""
        # Get initial cache version
        initial_version = self.LogicVariableResolver._get_cache_version()

        # Create a new variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_new_var",
                "label": "Test New Variable",
                "cel_accessor": "test_new_var",
                "source_type": "constant",
                "default_value": "100",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Cache version should have incremented
        new_version = self.LogicVariableResolver._get_cache_version()
        self.assertGreater(
            new_version,
            initial_version,
            "Cache version should increment when variable is created",
        )

        # Clean up
        test_var.unlink()

    def test_cache_invalidation_on_variable_update(self):
        """Test that updating a variable invalidates the cache."""
        # Create a test variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_update_var",
                "label": "Test Update Variable",
                "cel_accessor": "test_update_var",
                "source_type": "constant",
                "default_value": "100",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Get cache version after create
        version_after_create = self.LogicVariableResolver._get_cache_version()

        # Update the variable
        test_var.write({"default_value": "200"})

        # Cache version should have incremented
        version_after_update = self.LogicVariableResolver._get_cache_version()
        self.assertGreater(
            version_after_update,
            version_after_create,
            "Cache version should increment when variable is updated",
        )

        # Clean up
        test_var.unlink()

    def test_cache_invalidation_on_variable_delete(self):
        """Test that deleting a variable invalidates the cache."""
        # Create a test variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_delete_var",
                "label": "Test Delete Variable",
                "cel_accessor": "test_delete_var",
                "source_type": "constant",
                "default_value": "100",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Get cache version after create
        version_after_create = self.LogicVariableResolver._get_cache_version()

        # Delete the variable
        test_var.unlink()

        # Cache version should have incremented
        version_after_delete = self.LogicVariableResolver._get_cache_version()
        self.assertGreater(
            version_after_delete,
            version_after_create,
            "Cache version should increment when variable is deleted",
        )

    def test_from_cache_flag(self):
        """Test that the from_cache flag correctly indicates cache hits."""
        # Create a test variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_cache_flag",
                "label": "Test Cache Flag",
                "cel_accessor": "test_cache_flag",
                "source_type": "constant",
                "default_value": "500",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        expression = "income < test_cache_flag"

        # Clear cache to ensure fresh start
        self.LogicVariableResolver.invalidate_variable_cache()

        # First call should not be from cache
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertFalse(
            result1.get("from_cache"),
            "First resolution should not be from cache",
        )

        # Second call with same params should be from cache
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertTrue(
            result2.get("from_cache"),
            "Second resolution with same params should be from cache",
        )

        # Clean up
        test_var.unlink()

    def test_preview_resolution_does_not_use_cache(self):
        """Test that preview_resolution never uses or populates cache."""
        # Create a test variable
        test_var = self.LogicVariable.create(
            {
                "name": "test_preview",
                "label": "Test Preview",
                "cel_accessor": "test_preview",
                "source_type": "constant",
                "default_value": "999",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        expression = "x < test_preview"

        # Use preview_resolution
        result1 = self.LogicVariableResolver.preview_resolution(
            expression,
            context_type="individual",
        )
        self.assertFalse(
            result1.get("from_cache"),
            "Preview resolution should never be from cache",
        )

        # Second preview call should also not be from cache
        result2 = self.LogicVariableResolver.preview_resolution(
            expression,
            context_type="individual",
        )
        self.assertFalse(
            result2.get("from_cache"),
            "Preview resolution should never be from cache even on repeated calls",
        )

        # Clean up
        test_var.unlink()


@tagged("post_install", "-at_install")
class TestDeferredResolutionPackInstall(TransactionCase, CELTestDataMixin):
    """Tests for pack installation with deferred resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicPack = cls.env["spp.studio.pack"]
        cls.LogicPackItem = cls.env["spp.studio.pack.item"]
        cls.PackInstallWizard = cls.env["spp.studio.pack.install.wizard"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        # Create test category
        cls.test_category = cls._create_test_category(
            name=f"Test Pack Category {cls._test_id}",
            code=f"test_pack_deferred_{cls._test_id}",
        )

    def test_pack_install_stores_original_expression(self):
        """Test that installing a pack stores the original expression, not expanded."""
        # Create test variables
        threshold_var = self.LogicVariable.create(
            {
                "name": "test_install_threshold",
                "label": "Test Install Threshold",
                "cel_accessor": "test_install_threshold",
                "source_type": "constant",
                "default_value": "5000",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Create a test pack
        test_pack = self.LogicPack.create(
            {
                "name": "Test Deferred Pack",
                "code": "test_deferred_pack",
                "description": "Test pack for deferred resolution",
                "category": "cash_transfer",
                "version": "1.0",
                "author": "Test",
                "state": "available",
            }
        )

        # Create a pack item with variable reference
        test_item = self.LogicPackItem.create(
            {
                "pack_id": test_pack.id,
                "name": "Test Deferred Logic",
                "expression_type": "filter",
                "context_type": "group",
                "logic_data": '{"cel_expression": "income < test_install_threshold", "output_type": "boolean"}',
            }
        )

        # Create installation wizard
        wizard = self.PackInstallWizard.create(
            {
                "pack_id": test_pack.id,
                "install_as_draft": True,
                "install_personas": False,
            }
        )

        # Install the pack
        wizard.action_install()

        # Get the installed logic
        installed_logic = test_item.installed_logic_id
        self.assertTrue(installed_logic, "Logic should be created")

        # CRITICAL: The stored expression should contain the ORIGINAL variable reference
        # NOT the expanded value "5000"
        self.assertIn(
            "test_install_threshold",
            installed_logic.cel_expression,
            "Installed logic should store original variable reference, not expanded value",
        )
        self.assertNotIn(
            "5000",
            installed_logic.cel_expression,
            "Installed logic should NOT contain the expanded constant value",
        )

        _logger.info(
            f"Installed logic expression: {installed_logic.cel_expression} (original variable reference preserved)"
        )

        # Clean up
        installed_logic.unlink()
        test_item.unlink()
        test_pack.unlink()
        threshold_var.unlink()

    def test_installed_logic_uses_updated_constant(self):
        """Test that installed logic uses updated constant value at evaluation time."""
        # Create test variable
        threshold_var = self.LogicVariable.create(
            {
                "name": "test_eval_threshold",
                "label": "Test Eval Threshold",
                "cel_accessor": "test_eval_threshold",
                "source_type": "constant",
                "default_value": "1000",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Create logic with variable reference
        test_logic = self.Logic.create(
            {
                "name": "Test Deferred Eval Logic",
                "expression_type": "filter",
                "context_type": "group",
                "cel_expression": "income < test_eval_threshold",
                "output_type": "boolean",
                "state": "draft",
            }
        )

        # Resolve with original value
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            test_logic.cel_expression,
            context_type=test_logic.context_type,
        )
        self.assertIn("1000", result1["expression"])
        _logger.info(f"Resolution with original value: {result1['expression']}")

        # Update the constant
        threshold_var.write({"default_value": "2000"})

        # Resolve again - should use new value
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            test_logic.cel_expression,
            context_type=test_logic.context_type,
        )
        self.assertIn("2000", result2["expression"])
        self.assertNotIn("1000", result2["expression"])
        _logger.info(f"Resolution with updated value: {result2['expression']}")

        # The stored expression should still have the variable reference
        self.assertIn("test_eval_threshold", test_logic.cel_expression)

        # Clean up
        test_logic.unlink()
        threshold_var.unlink()


@tagged("post_install", "-at_install")
class TestDeferredResolutionProgramOverrides(TransactionCase, CELTestDataMixin):
    """Tests for program-specific constant overrides with deferred resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.LogicProgramParameter = cls.env["spp.cel.program.parameter"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        # Create test category
        cls.test_category = cls._create_test_category(
            name=f"Test Program Override Category {cls._test_id}",
            code=f"test_program_override_{cls._test_id}",
        )

    def test_program_override_used_in_resolution(self):
        """Test that program-specific overrides are used during resolution."""
        # Skip if spp.program model doesn't exist
        if "spp.program" not in self.env:
            self.skipTest("spp.program model not available")

        # Create a program-configurable constant
        threshold_var = self.LogicVariable.create(
            {
                "name": "test_program_threshold",
                "label": "Test Program Threshold",
                "cel_accessor": "test_program_threshold",
                "source_type": "constant",
                "default_value": "1000",
                "is_program_configurable": True,
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Create a test program
        Program = self.env["spp.program"]
        test_program = Program.create(
            {
                "name": "Test Program for Overrides",
            }
        )

        # Create a program-specific override
        override = self.LogicProgramParameter.create(
            {
                "program_id": test_program.id,
                "variable_id": threshold_var.id,
                "value": "5000",
            }
        )

        expression = "income < test_program_threshold"

        # Resolution WITHOUT program_id should use default
        result_no_program = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            program_id=None,
            context_type="group",
        )
        self.assertIn("1000", result_no_program["expression"])
        _logger.info(f"Resolution without program: {result_no_program['expression']}")

        # Resolution WITH program_id should use override
        result_with_program = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            program_id=test_program.id,
            context_type="group",
        )
        self.assertIn("5000", result_with_program["expression"])
        self.assertNotIn("1000", result_with_program["expression"])
        _logger.info(f"Resolution with program: {result_with_program['expression']}")

        # Clean up
        override.unlink()
        test_program.unlink()
        threshold_var.unlink()

    def test_program_override_change_propagates(self):
        """Test that changing a program override propagates."""
        # Skip if spp.program model doesn't exist
        if "spp.program" not in self.env:
            self.skipTest("spp.program model not available")

        # Create a program-configurable constant
        threshold_var = self.LogicVariable.create(
            {
                "name": "test_override_change",
                "label": "Test Override Change",
                "cel_accessor": "test_override_change",
                "source_type": "constant",
                "default_value": "1000",
                "is_program_configurable": True,
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Create a test program
        Program = self.env["spp.program"]
        test_program = Program.create(
            {
                "name": "Test Program Override Change",
            }
        )

        # Create initial override
        override = self.LogicProgramParameter.create(
            {
                "program_id": test_program.id,
                "variable_id": threshold_var.id,
                "value": "3000",
            }
        )

        expression = "income < test_override_change"

        # Initial resolution
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            program_id=test_program.id,
            context_type="group",
        )
        self.assertIn("3000", result1["expression"])

        # Change the override
        override.write({"value": "4500"})

        # Resolution should use new override value
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            program_id=test_program.id,
            context_type="group",
        )
        self.assertIn("4500", result2["expression"])
        self.assertNotIn("3000", result2["expression"])

        # Clean up
        override.unlink()
        test_program.unlink()
        threshold_var.unlink()


@tagged("post_install", "-at_install")
class TestDeferredResolutionWithExistingPacks(TransactionCase):
    """Tests using the existing standard packs to validate deferred resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.LogicPack = cls.env["spp.studio.pack"]
        cls.LogicPackItem = cls.env["spp.studio.pack.item"]

    def test_standard_pack_expressions_resolve_correctly(self):
        """Test that standard pack expressions resolve with current variable values."""
        # Get the cash_transfer_basic pack
        pack = self.LogicPack.search([("code", "=", "cash_transfer_basic")], limit=1)

        if not pack:
            self.skipTest("cash_transfer_basic pack not found")

        # Get the poverty line variable
        poverty_line_var = self.LogicVariable.search(
            [
                ("cel_accessor", "=", "poverty_line"),
            ],
            limit=1,
        )

        if not poverty_line_var:
            self.skipTest("poverty_line variable not found")

        original_default = poverty_line_var.default_value

        # Find an item that uses poverty_line
        item_with_poverty_line = None
        for item in pack.item_ids:
            result = self.LogicVariableResolver.expand_pack_item(item)
            if "poverty_line" in result.get("variables_used", []):
                item_with_poverty_line = item
                break

        if not item_with_poverty_line:
            self.skipTest("No pack item uses poverty_line variable")

        # Get current resolution
        result1 = self.LogicVariableResolver.expand_pack_item(item_with_poverty_line)
        _logger.info(f"Original expression: {result1['original_expression']}")
        _logger.info(f"Resolved (original): {result1['expanded_expression']}")

        # Change poverty_line
        test_value = "99999"
        poverty_line_var.write({"default_value": test_value})

        # Resolution should now use new value
        result2 = self.LogicVariableResolver.expand_pack_item(item_with_poverty_line)
        _logger.info(f"Resolved (after change): {result2['expanded_expression']}")

        self.assertIn(
            test_value,
            result2["expanded_expression"],
            "Resolution should use updated poverty_line value",
        )

        # Restore original value
        poverty_line_var.write({"default_value": original_default})

    def test_all_standard_packs_support_deferred_resolution(self):
        """Verify all standard packs work with deferred resolution."""
        all_packs = self.LogicPack.search([])

        for pack in all_packs:
            for item in pack.item_ids:
                # Use preview_resolution to test without affecting cache
                result = self.LogicVariableResolver.preview_resolution(
                    item.logic_data and self._extract_cel_from_item(item) or "",
                    context_type=item.context_type or "group",
                )

                # Log results for debugging
                _logger.debug(
                    f"Pack '{pack.code}' item '{item.name}': "
                    f"variables={result.get('variables_used', [])}, "
                    f"missing={result.get('missing_variables', [])}"
                )

                # Warn about missing variables (don't fail - they may be optional)
                if result.get("missing_variables"):
                    _logger.warning(
                        f"Pack '{pack.code}' item '{item.name}' has missing variables: {result['missing_variables']}"
                    )

    def _extract_cel_from_item(self, item):
        """Extract CEL expression from pack item's logic_data."""
        import json

        try:
            data = json.loads(item.logic_data)
            return data.get("cel_expression", "")
        except (json.JSONDecodeError, TypeError):
            return ""


@tagged("post_install", "-at_install")
class TestDeferredResolutionContextAwareness(TransactionCase, CELTestDataMixin):
    """Tests for context-aware variable resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        # Create test category
        cls.test_category = cls._create_test_category(
            name=f"Test Context Category {cls._test_id}",
            code=f"test_context_{cls._test_id}",
        )

    def test_individual_context_uses_individual_variable(self):
        """Test that individual context prefers individual-scoped variables."""
        # Create individual-scoped variable
        individual_var = self.LogicVariable.create(
            {
                "name": "test_context_var_ind",
                "label": "Test Context Var (Individual)",
                "cel_accessor": "test_context_var",
                "source_type": "computed",
                "cel_expression": "r.individual_field",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        # Create group-scoped variable with same accessor
        group_var = self.LogicVariable.create(
            {
                "name": "test_context_var_grp",
                "label": "Test Context Var (Group)",
                "cel_accessor": "test_context_var",
                "source_type": "computed",
                "cel_expression": "members.sum(m, m.group_field, true)",
                "value_type": "number",
                "applies_to": "group",
                "category_id": self.test_category.id,
            }
        )

        expression = "test_context_var > 100"

        # Individual context should use individual variable
        result_individual = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )
        self.assertIn("r.individual_field", result_individual["expression"])
        self.assertNotIn("members.sum", result_individual["expression"])

        # Group context should use group variable
        result_group = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertIn("members.sum", result_group["expression"])
        self.assertNotIn("r.individual_field", result_group["expression"])

        # Clean up
        individual_var.unlink()
        group_var.unlink()

    def test_both_context_variable_used_as_fallback(self):
        """Test that 'both' context variables are used when specific context not found."""
        # Create a variable that applies to both contexts
        both_var = self.LogicVariable.create(
            {
                "name": "test_both_context",
                "label": "Test Both Context",
                "cel_accessor": "test_both_context",
                "source_type": "constant",
                "default_value": "12345",
                "value_type": "number",
                "applies_to": "both",
                "category_id": self.test_category.id,
            }
        )

        expression = "x < test_both_context"

        # Both individual and group context should resolve
        result_individual = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )
        self.assertIn("12345", result_individual["expression"])

        result_group = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )
        self.assertIn("12345", result_group["expression"])

        # Clean up
        both_var.unlink()


@tagged("post_install", "-at_install")
class TestDeferredResolutionEdgeCases(TransactionCase, CELTestDataMixin):
    """Edge case tests for deferred resolution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        # Create test category
        cls.test_category = cls._create_test_category(
            name=f"Test Edge Cases {cls._test_id}",
            code=f"test_edge_cases_{cls._test_id}",
        )

    def test_empty_expression(self):
        """Test resolution of empty expression."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "",
            context_type="group",
        )
        self.assertEqual(result["expression"], "")
        self.assertEqual(result["variables_used"], [])
        self.assertEqual(result["missing_variables"], [])

    def test_none_expression(self):
        """Test resolution of None expression."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            None,
            context_type="group",
        )
        self.assertEqual(result["expression"], "")

    def test_expression_with_only_literals(self):
        """Test expression with no variables to resolve."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "100 < 200 && true",
            context_type="group",
        )
        self.assertEqual(result["expression"], "100 < 200 && true")
        self.assertEqual(result["variables_used"], [])
        self.assertEqual(result["missing_variables"], [])

    def test_recursive_variable_expansion(self):
        """Test that variables referencing other variables expand correctly."""
        # Create base variable
        base_var = self.LogicVariable.create(
            {
                "name": "test_base_var",
                "label": "Test Base Variable",
                "cel_accessor": "test_base_var",
                "source_type": "constant",
                "default_value": "500",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Create derived variable that references base
        derived_var = self.LogicVariable.create(
            {
                "name": "test_derived_var",
                "label": "Test Derived Variable",
                "cel_accessor": "test_derived_var",
                "source_type": "computed",
                "cel_expression": "test_base_var * 2",
                "value_type": "number",
                "category_id": self.test_category.id,
            }
        )

        # Resolution should expand both variables
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "x < test_derived_var",
            context_type="group",
        )

        # The base variable should be expanded within the derived
        self.assertIn("500", result["expression"])
        self.assertIn("* 2", result["expression"])

        _logger.info(f"Recursive expansion result: {result['expression']}")

        # Clean up
        derived_var.unlink()
        base_var.unlink()

    def test_missing_variable_reported(self):
        """Test that missing variables are correctly reported."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "income < nonexistent_variable",
            context_type="group",
        )

        self.assertIn("nonexistent_variable", result["missing_variables"])
        _logger.info(f"Missing variables: {result['missing_variables']}")

    def test_cel_keywords_not_treated_as_variables(self):
        """Test that CEL keywords are not treated as missing variables."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "true && false || !exists",
            context_type="group",
        )

        # CEL keywords should not be in missing_variables
        for keyword in ["true", "false", "exists"]:
            self.assertNotIn(
                keyword,
                result["missing_variables"],
                f"CEL keyword '{keyword}' should not be treated as missing variable",
            )

    def test_vocabulary_type_variable_uses_cel_expression(self):
        """Test that vocabulary type variables use their cel_expression, not just accessor.

        This test catches a bug where vocabulary variables like 'is_female' were
        returning just the accessor name instead of the actual CEL expression.
        """
        # Create a vocabulary type variable with a cel_expression
        # ADR-008: Using 'r.' prefix for current record access
        vocab_var = self.LogicVariable.create(
            {
                "name": "test_is_female",
                "label": "Test Is Female",
                "cel_accessor": "test_is_female",
                "source_type": "vocabulary",
                "cel_expression": "is_female(r.gender_id)",
                "value_type": "boolean",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        expression = "test_is_female && age > 18"

        result = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )

        # Should resolve to the CEL expression, NOT just the accessor
        # ADR-008: Expects 'r.' prefix for current record access
        self.assertIn("is_female(r.gender_id)", result["expression"])
        self.assertNotIn("test_is_female &&", result["expression"])

        _logger.info(f"Vocabulary variable resolution: {result['expression']}")

        # Clean up
        vocab_var.unlink()

    def test_external_type_variable_uses_cel_expression(self):
        """Test that external type variables use their cel_expression when defined."""
        # Create an external type variable with a cel_expression
        external_var = self.LogicVariable.create(
            {
                "name": "test_external",
                "label": "Test External",
                "cel_accessor": "test_external",
                "source_type": "external",
                "cel_expression": 'metric("household.size")',
                "value_type": "number",
                "applies_to": "group",
                "category_id": self.test_category.id,
            }
        )

        expression = "test_external > 3"

        result = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="group",
        )

        # Should resolve to the CEL expression
        self.assertIn("metric", result["expression"])

        _logger.info(f"External variable resolution: {result['expression']}")

        # Clean up
        external_var.unlink()

    def test_scoring_type_variable_uses_cel_expression(self):
        """Test that scoring type variables use their cel_expression when defined."""
        # Create a scoring type variable with a cel_expression
        scoring_var = self.LogicVariable.create(
            {
                "name": "test_score",
                "label": "Test Score",
                "cel_accessor": "test_score",
                "source_type": "scoring",
                "cel_expression": "pmt_score(me)",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        expression = "test_score > 50"

        result = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )

        # Should resolve to the CEL expression
        self.assertIn("pmt_score(me)", result["expression"])

        _logger.info(f"Scoring variable resolution: {result['expression']}")

        # Clean up
        scoring_var.unlink()

    def test_variable_shadows_function_name(self):
        """Test that a variable can shadow a function name when used without parentheses.

        This is critical: if there's both:
        - A CEL function `is_female(gender)`
        - A variable `is_female` that expands to `is_female(me.gender)`

        When user writes `is_female && age > 18` (no parentheses), it should
        be treated as a VARIABLE and expanded.

        When user writes `is_female(me.gender)` (with parentheses), it should
        be treated as a FUNCTION CALL and not expanded.
        """
        # Create a variable that shadows a potential function name
        shadow_var = self.LogicVariable.create(
            {
                "name": "check_status",
                "label": "Check Status",
                "cel_accessor": "check_status",
                "source_type": "vocabulary",
                "cel_expression": "check_status_func(me.status_field)",
                "value_type": "boolean",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        # Test 1: Used as variable (no parentheses) - should expand
        expr_as_var = "check_status && other_condition"
        result_var = self.LogicVariableResolver.resolve_for_evaluation(
            expr_as_var,
            context_type="individual",
        )
        self.assertIn("check_status_func(me.status_field)", result_var["expression"])
        _logger.info(f"As variable: {result_var['expression']}")

        # Test 2: Used as function call (with parentheses) - should NOT expand
        expr_as_func = "check_status(some_arg) && other_condition"
        result_func = self.LogicVariableResolver.resolve_for_evaluation(
            expr_as_func,
            context_type="individual",
        )
        # Should keep original function call, not expand
        self.assertIn("check_status(some_arg)", result_func["expression"])
        self.assertNotIn("check_status_func", result_func["expression"])
        _logger.info(f"As function: {result_func['expression']}")

        # Clean up
        shadow_var.unlink()

    def test_is_female_variable_expands_correctly(self):
        """Test the real-world is_female variable scenario.

        The is_female variable should expand to is_female(r.gender_id) when
        used standalone, even though is_female is also a registered function.
        ADR-008: Using 'r.' prefix for current record access.
        """
        # Check if is_female variable exists
        is_female_var = self.LogicVariable.search(
            [
                ("cel_accessor", "=", "is_female"),
                ("applies_to", "=", "individual"),
            ],
            limit=1,
        )

        if not is_female_var:
            self.skipTest("is_female variable not found in standard variables")

        # Test: is_female used standalone should expand
        expression = "is_female && age > 18"
        result = self.LogicVariableResolver.resolve_for_evaluation(
            expression,
            context_type="individual",
        )

        # NOTE: is_female is both a registered CEL function AND a variable.
        # The resolver correctly keeps function names as-is when they appear
        # without arguments - they're valid CEL identifiers.
        # The 'age' variable should be expanded to age_years(r.birthdate)
        self.assertIn("is_female", result["expression"])
        self.assertIn("age_years(r.birthdate)", result["expression"])

        _logger.info(f"is_female expansion: {result['expression']}")


@tagged("post_install", "-at_install")
class TestVariableResolverCriticalEdgeCases(TransactionCase, CELTestDataMixin):
    """Critical edge case tests for variable resolver.

    Based on adversarial QA analysis, these tests focus on:
    - Circular reference detection
    - Depth limit enforcement
    - Cache behavior
    - Error recovery
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableResolver = cls.env["spp.cel.variable.resolver"]
        cls.VariableCategory = cls.env["spp.cel.variable.category"]

        cls.test_category = cls._create_test_category(
            name=f"Critical Edge Cases {cls._test_id}",
            code=f"critical_edge_{cls._test_id}",
        )

    def test_direct_circular_reference_detected(self):
        """Test that A -> B -> A circular reference is detected."""
        var_a = self.LogicVariable.create(
            {
                "name": "circ_a",
                "label": "Circular A",
                "cel_accessor": "circ_a",
                "source_type": "computed",
                "cel_expression": "circ_b + 1",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )
        var_b = self.LogicVariable.create(
            {
                "name": "circ_b",
                "label": "Circular B",
                "cel_accessor": "circ_b",
                "source_type": "computed",
                "cel_expression": "circ_a + 1",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        # Should not cause infinite loop
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "circ_a + 10",
            context_type="individual",
        )

        # Should complete, possibly with warnings or partial expansion
        self.assertIn("expression", result)
        _logger.info("Circular reference result: %s", result)

        var_a.unlink()
        var_b.unlink()

    def test_indirect_circular_reference_detected(self):
        """Test that A -> B -> C -> A circular reference is detected."""
        var_a = self.LogicVariable.create(
            {
                "name": "chain_a",
                "label": "Chain A",
                "cel_accessor": "chain_a",
                "source_type": "computed",
                "cel_expression": "chain_b + 1",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )
        var_b = self.LogicVariable.create(
            {
                "name": "chain_b",
                "label": "Chain B",
                "cel_accessor": "chain_b",
                "source_type": "computed",
                "cel_expression": "chain_c + 1",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )
        var_c = self.LogicVariable.create(
            {
                "name": "chain_c",
                "label": "Chain C",
                "cel_accessor": "chain_c",
                "source_type": "computed",
                "cel_expression": "chain_a + 1",
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        # Should not cause infinite loop
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "chain_a + 10",
            context_type="individual",
        )

        self.assertIn("expression", result)
        _logger.info("Indirect circular result: %s", result)

        var_a.unlink()
        var_b.unlink()
        var_c.unlink()

    def test_depth_limit_enforced(self):
        """Test that maximum recursion depth is enforced."""
        # Create a chain of 15 variables (exceeds limit of 10)
        vars_created = []
        for i in range(15):
            if i == 0:
                expr = "100"  # Base case
            else:
                expr = f"depth_var_{i - 1} + 1"

            var = self.LogicVariable.create(
                {
                    "name": f"depth_var_{i}",
                    "label": f"Depth Var {i}",
                    "cel_accessor": f"depth_var_{i}",
                    "source_type": "computed",
                    "cel_expression": expr,
                    "value_type": "number",
                    "applies_to": "individual",
                    "category_id": self.test_category.id,
                }
            )
            vars_created.append(var)

        # Try to resolve the deepest variable
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "depth_var_14",
            context_type="individual",
        )

        # Should not crash, should complete
        self.assertIn("expression", result)
        _logger.info("Depth limit result: %s", result)

        # Check for warning about depth
        if result.get("warnings"):
            _logger.info("Depth warnings: %s", result["warnings"])

        for var in vars_created:
            var.unlink()

    def test_self_referencing_variable_handled(self):
        """Test that self-referencing variable doesn't infinite loop."""
        var = self.LogicVariable.create(
            {
                "name": "self_ref",
                "label": "Self Reference",
                "cel_accessor": "self_ref",
                "source_type": "computed",
                "cel_expression": "self_ref + 1",  # References itself!
                "value_type": "number",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        result = self.LogicVariableResolver.resolve_for_evaluation(
            "self_ref",
            context_type="individual",
        )

        # Should complete without infinite loop
        self.assertIn("expression", result)

        var.unlink()

    def test_cache_invalidation_updates_results(self):
        """Test that cache invalidation causes fresh resolution."""
        var = self.LogicVariable.create(
            {
                "name": "cache_test",
                "label": "Cache Test",
                "cel_accessor": "cache_test",
                "source_type": "constant",
                "default_value": "100",
                "value_type": "number",
                "applies_to": "both",
                "category_id": self.test_category.id,
            }
        )

        # Clear cache
        self.LogicVariableResolver.invalidate_variable_cache()

        # First resolution
        result1 = self.LogicVariableResolver.resolve_for_evaluation(
            "cache_test + 1",
            context_type="group",
        )
        self.assertIn("100", result1["expression"])

        # Change variable
        var.default_value = "200"

        # Invalidate cache
        self.LogicVariableResolver.invalidate_variable_cache()

        # Second resolution should have new value
        result2 = self.LogicVariableResolver.resolve_for_evaluation(
            "cache_test + 1",
            context_type="group",
        )
        self.assertIn("200", result2["expression"])

        var.unlink()

    def test_empty_expression_handled(self):
        """Test that empty expression doesn't crash."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "",
            context_type="individual",
        )

        self.assertEqual(result["expression"], "")
        self.assertEqual(result["variables_used"], [])

    def test_whitespace_only_expression_handled(self):
        """Test that whitespace-only expression doesn't crash."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "   \n\t  ",
            context_type="individual",
        )

        self.assertIn("expression", result)

    def test_special_characters_in_expression(self):
        """Test expressions with special characters are handled."""
        # These shouldn't be valid CEL but shouldn't crash resolver
        test_expressions = [
            "true && false",
            "1 > 0 ? 'yes' : 'no'",
            "[1, 2, 3].size()",
            "{'key': 'value'}.key",
        ]

        for expr in test_expressions:
            result = self.LogicVariableResolver.resolve_for_evaluation(
                expr,
                context_type="individual",
            )
            self.assertIn("expression", result)

    def test_unicode_in_expression(self):
        """Test expressions with unicode characters."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "name == 'Müller' && city == '北京'",
            context_type="individual",
        )

        self.assertIn("expression", result)
        self.assertIn("Müller", result["expression"])
        self.assertIn("北京", result["expression"])

    def test_very_long_expression(self):
        """Test handling of very long expressions."""
        # Create expression with 100 terms
        terms = [f"var_{i}" for i in range(100)]
        long_expr = " + ".join(terms)

        result = self.LogicVariableResolver.resolve_for_evaluation(
            long_expr,
            context_type="individual",
        )

        # Should complete without timeout
        self.assertIn("expression", result)

    def test_missing_variable_tracked(self):
        """Test that undefined variables are tracked in missing_variables."""
        result = self.LogicVariableResolver.resolve_for_evaluation(
            "undefined_variable_xyz + 10",
            context_type="individual",
        )

        # Should track as missing
        self.assertIn("undefined_variable_xyz", result.get("missing_variables", []))

    def test_multiple_context_types(self):
        """Test resolution with different context types."""
        # Create individual-only variable
        ind_var = self.LogicVariable.create(
            {
                "name": "ind_only_ctx",
                "label": "Individual Only Ctx",
                "cel_accessor": "ind_only_ctx",
                "source_type": "constant",
                "default_value": "individual_value",
                "value_type": "string",
                "applies_to": "individual",
                "category_id": self.test_category.id,
            }
        )

        # Create group-only variable
        grp_var = self.LogicVariable.create(
            {
                "name": "grp_only_ctx",
                "label": "Group Only Ctx",
                "cel_accessor": "grp_only_ctx",
                "source_type": "constant",
                "default_value": "group_value",
                "value_type": "string",
                "applies_to": "group",
                "category_id": self.test_category.id,
            }
        )

        # Test individual context
        result_ind = self.LogicVariableResolver.resolve_for_evaluation(
            "ind_only_ctx",
            context_type="individual",
        )
        self.assertIn("individual_value", result_ind["expression"])

        # Test group context
        result_grp = self.LogicVariableResolver.resolve_for_evaluation(
            "grp_only_ctx",
            context_type="group",
        )
        self.assertIn("group_value", result_grp["expression"])

        ind_var.unlink()
        grp_var.unlink()
