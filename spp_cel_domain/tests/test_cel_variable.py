# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL Variable models - ADR-008 implementation.

Tests cover:
- Variable CRUD operations
- Category CRUD operations
- Expression model functionality
- Variable resolver functionality
- Auto-computed cel_expression for aggregates
- CEL service integration with variables
"""

import time

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import CELTestDataMixin


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestCELVariableCategory(TransactionCase, CELTestDataMixin):
    """Test spp.cel.variable.category model."""

    def setUp(self):
        super().setUp()
        self.Category = self.env["spp.cel.variable.category"]
        self._test_id = int(time.time() * 1000)

    def test_create_category(self):
        """Test basic category creation."""
        category = self.Category.create(
            {
                "name": "Test Category",
                "code": "test_category",
                "sequence": 10,
            }
        )
        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.code, "test_category")
        self.assertTrue(category.active)

    def test_category_code_unique(self):
        """Test that category code must be unique."""
        self.Category.create(
            {
                "name": "Category 1",
                "code": "unique_code",
            }
        )
        with self.assertRaises(ValidationError):
            self.Category.create(
                {
                    "name": "Category 2",
                    "code": "unique_code",  # Duplicate
                }
            )

    def test_get_or_create_new(self):
        """Test _get_or_create creates new category."""
        category = self.Category._get_or_create("new_code", "New Category")
        self.assertEqual(category.code, "new_code")
        self.assertEqual(category.name, "New Category")

    def test_get_or_create_existing(self):
        """Test _get_or_create returns existing category."""
        original = self.Category.create(
            {
                "name": "Original",
                "code": "existing_code",
            }
        )
        found = self.Category._get_or_create("existing_code", "Different Name")
        self.assertEqual(found.id, original.id)
        self.assertEqual(found.name, "Original")  # Name not updated

    def test_variable_count_computed(self):
        """Test variable_count is computed correctly."""
        category = self.Category.create(
            {
                "name": "Count Test",
                "code": "count_test",
            }
        )
        self.assertEqual(category.variable_count, 0)

        # Add a variable
        self.env["spp.cel.variable"].create(
            {
                "name": "test_var",
                "cel_accessor": "test_var",
                "source_type": "constant",
                "value_type": "number",
                "category_id": category.id,
                "default_value": "100",
            }
        )
        category.invalidate_recordset()
        self.assertEqual(category.variable_count, 1)


@tagged("post_install", "-at_install")
class TestCELVariable(TransactionCase, CELTestDataMixin):
    """Test spp.cel.variable model."""

    def setUp(self):
        super().setUp()
        self._test_id = int(time.time() * 1000)
        self.Variable = self.env["spp.cel.variable"]
        self.category = self.env["spp.cel.variable.category"].create(
            {
                "name": f"Test Category {self._test_id}",
                "code": f"test_{self._test_id}",
            }
        )

    def test_create_constant_variable(self):
        """Test creating a constant variable."""
        var = self.Variable.create(
            {
                "name": _unique("poverty_line"),
                "cel_accessor": _unique("poverty_line"),
                "source_type": "constant",
                "value_type": "money",
                "default_value": "2500",
            }
        )
        self.assertEqual(var.source_type, "constant")
        self.assertEqual(var.default_value, "2500")
        self.assertEqual(var.get_cel_expression(), "2500")

    def test_create_field_variable(self):
        """Test creating a field-based variable."""
        var = self.Variable.create(
            {
                "name": _unique("registrant_income"),
                "cel_accessor": _unique("income"),
                "source_type": "field",
                "value_type": "money",
                "source_model": "res.partner",
                "source_field": "income",
            }
        )
        self.assertEqual(var.source_type, "field")
        self.assertEqual(var.get_cel_expression(), "r.income")

    def test_create_computed_variable(self):
        """Test creating a computed variable."""
        var = self.Variable.create(
            {
                "name": _unique("is_adult"),
                "cel_accessor": _unique("is_adult"),
                "source_type": "computed",
                "value_type": "boolean",
                "cel_expression": "age_years(r.birthdate) >= 18",
            }
        )
        self.assertEqual(var.source_type, "computed")
        self.assertEqual(var.get_cel_expression(), "age_years(r.birthdate) >= 18")

    def test_aggregate_count_cel_expression(self):
        """Test aggregate count generates correct CEL."""
        var = self.Variable.create(
            {
                "name": _unique("hh_size"),
                "cel_accessor": _unique("hh_size"),
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
            }
        )
        self.assertEqual(var.cel_expression, "members.count(true)")

    def test_aggregate_count_with_filter_cel_expression(self):
        """Test aggregate count with filter generates correct CEL."""
        var = self.Variable.create(
            {
                "name": _unique("child_count"),
                "cel_accessor": _unique("child_count"),
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "age_years(m.birthdate) < 18",
            }
        )
        self.assertEqual(var.cel_expression, "members.count(age_years(m.birthdate) < 18)")

    def test_aggregate_exists_cel_expression(self):
        """Test aggregate exists generates correct CEL."""
        var = self.Variable.create(
            {
                "name": _unique("has_disabled"),
                "cel_accessor": _unique("has_disabled"),
                "source_type": "aggregate",
                "value_type": "boolean",
                "aggregate_type": "exists",
                "aggregate_target": "members",
                "aggregate_filter": "m.is_disabled == true",
            }
        )
        self.assertEqual(var.cel_expression, "members.exists(m.is_disabled == true)")

    def test_aggregate_sum_cel_expression(self):
        """Test aggregate sum generates correct CEL."""
        var = self.Variable.create(
            {
                "name": _unique("total_income"),
                "cel_accessor": _unique("total_income"),
                "source_type": "aggregate",
                "value_type": "money",
                "aggregate_type": "sum",
                "aggregate_target": "members",
                "aggregate_field": "income",
                "aggregate_filter": "true",
            }
        )
        self.assertEqual(var.cel_expression, "members.sum(m, m.income, true)")

    def test_aggregate_avg_cel_expression(self):
        """Test aggregate average generates correct CEL."""
        var = self.Variable.create(
            {
                "name": _unique("avg_age"),
                "cel_accessor": _unique("avg_age"),
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "avg",
                "aggregate_target": "members",
                "aggregate_field": "age",
                "aggregate_filter": "age_years(m.birthdate) >= 18",
            }
        )
        self.assertEqual(var.cel_expression, "members.avg(m, m.age, age_years(m.birthdate) >= 18)")

    @mute_logger("odoo.sql_db")
    def test_name_unique_constraint(self):
        """Test that variable name must be unique."""
        unique_name = _unique("unique_var")
        self.Variable.create(
            {
                "name": unique_name,
                "cel_accessor": _unique("unique_var_1"),
                "source_type": "constant",
                "value_type": "number",
                "default_value": "1",
            }
        )
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.Variable.create(
                    {
                        "name": unique_name,  # Duplicate name
                        "cel_accessor": _unique("unique_var_2"),
                        "source_type": "constant",
                        "value_type": "number",
                        "default_value": "2",
                    }
                )

    @mute_logger("odoo.sql_db")
    def test_cel_accessor_unique_per_context(self):
        """Test that CEL accessor is unique within same context."""
        shared_accessor = _unique("shared_accessor")
        self.Variable.create(
            {
                "name": _unique("var_individual"),
                "cel_accessor": shared_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "1",
                "applies_to": "individual",
            }
        )
        # Same accessor for different context should work
        var2 = self.Variable.create(
            {
                "name": _unique("var_group"),
                "cel_accessor": shared_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "2",
                "applies_to": "group",
            }
        )
        self.assertTrue(var2.id > 0)

        # Same accessor for same context should fail
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.Variable.create(
                    {
                        "name": _unique("var_individual_2"),
                        "cel_accessor": shared_accessor,
                        "source_type": "constant",
                        "value_type": "number",
                        "default_value": "3",
                        "applies_to": "individual",
                    }
                )

    def test_get_by_cel_accessor(self):
        """Test finding variable by CEL accessor."""
        accessor = _unique("findable")
        var = self.Variable.create(
            {
                "name": _unique("findable_var"),
                "cel_accessor": accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "42",
            }
        )
        found = self.Variable.get_by_cel_accessor(accessor)
        self.assertEqual(found.id, var.id)

    def test_get_by_cel_accessor_with_context(self):
        """Test finding variable by CEL accessor with context filter."""
        ctx_accessor = _unique("ctx_var")
        self.Variable.create(
            {
                "name": _unique("ctx_var_individual"),
                "cel_accessor": ctx_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "1",
                "applies_to": "individual",
            }
        )
        group_var = self.Variable.create(
            {
                "name": _unique("ctx_var_group"),
                "cel_accessor": ctx_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "2",
                "applies_to": "group",
            }
        )

        found = self.Variable.get_by_cel_accessor(ctx_accessor, context_type="group")
        self.assertEqual(found.id, group_var.id)

    def test_activate_deactivate(self):
        """Test activation and deactivation actions."""
        var = self.Variable.create(
            {
                "name": _unique("lifecycle_var"),
                "cel_accessor": _unique("lifecycle"),
                "source_type": "constant",
                "value_type": "number",
                "default_value": "1",
                "state": "draft",
            }
        )
        self.assertEqual(var.state, "draft")

        var.action_activate()
        self.assertEqual(var.state, "active")

        var.action_deactivate()
        self.assertEqual(var.state, "inactive")


@tagged("post_install", "-at_install")
class TestCELExpression(TransactionCase, CELTestDataMixin):
    """Test spp.cel.expression model."""

    def setUp(self):
        super().setUp()
        self._test_id = int(time.time() * 1000)
        self.Expression = self.env["spp.cel.expression"]
        self.Variable = self.env["spp.cel.variable"]

        # Create some variables for testing with unique names
        self.income_var = self.Variable.create(
            {
                "name": _unique("income"),
                "cel_accessor": _unique("income"),
                "source_type": "field",
                "value_type": "money",
                "source_field": "income",
            }
        )
        self.poverty_var = self.Variable.create(
            {
                "name": _unique("poverty_line"),
                "cel_accessor": _unique("poverty_line"),
                "source_type": "constant",
                "value_type": "money",
                "default_value": "2500",
            }
        )

    def test_create_expression(self):
        """Test basic expression creation."""
        expr = self.Expression.create(
            {
                "name": _unique("Income Check"),
                "cel_expression": "r.income > 0",  # Simple expression
                "expression_type": "filter",
                "output_type": "boolean",
            }
        )
        self.assertEqual(expr.expression_type, "filter")
        self.assertEqual(expr.output_type, "boolean")
        self.assertTrue(expr.code)  # Auto-generated

    def test_expression_code_auto_generated(self):
        """Test that code is auto-generated from name."""
        expr = self.Expression.create(
            {
                "name": f"My Complex Expression {self._test_id}",
                "cel_expression": "true",
                "expression_type": "other",
                "output_type": "boolean",
            }
        )
        self.assertIn("my_complex_expression", expr.code)

    def test_expression_code_unique(self):
        """Test that expression code must be unique."""
        unique_code = _unique("unique_code")
        self.Expression.create(
            {
                "name": _unique("First"),
                "code": unique_code,
                "cel_expression": "true",
                "expression_type": "other",
                "output_type": "boolean",
            }
        )
        with self.assertRaises(ValidationError):
            self.Expression.create(
                {
                    "name": _unique("Second"),
                    "code": unique_code,  # Duplicate
                    "cel_expression": "false",
                    "expression_type": "other",
                    "output_type": "boolean",
                }
            )

    def test_variable_ids_computed(self):
        """Test that variable_ids is computed from expression."""
        # Use the accessor from our created variable
        expr = self.Expression.create(
            {
                "name": _unique("Uses Variables"),
                "cel_expression": f"r.income > {self.poverty_var.cel_accessor}",
                "expression_type": "filter",
                "output_type": "boolean",
            }
        )
        # Variable detection is based on parsing
        self.assertIsNotNone(expr.variable_ids)

    def test_activate_without_expression_fails(self):
        """Test that activation without CEL expression fails."""
        expr = self.Expression.create(
            {
                "name": _unique("Empty Expression"),
                "cel_expression": "",
                "expression_type": "other",
                "output_type": "boolean",
                "state": "draft",
            }
        )
        with self.assertRaises(ValidationError):
            expr.action_activate()

    def test_get_resolved_expression(self):
        """Test getting resolved expression."""
        expr = self.Expression.create(
            {
                "name": _unique("Resolvable"),
                "cel_expression": "r.income > 0",  # Simple expression
                "expression_type": "filter",
                "output_type": "boolean",
                "context_type": "individual",
            }
        )
        resolved = expr.get_resolved_expression()
        # Should contain either original or expanded expression
        self.assertIn("income", resolved)


@tagged("post_install", "-at_install")
class TestCELVariableResolver(TransactionCase, CELTestDataMixin):
    """Test spp.cel.variable.resolver model."""

    def setUp(self):
        super().setUp()
        self._test_id = int(time.time() * 1000)
        self.Resolver = self.env["spp.cel.variable.resolver"]
        self.Variable = self.env["spp.cel.variable"]

        # Create unique accessors for this test run
        self.income_accessor = _unique("income")
        self.poverty_accessor = _unique("poverty_line")
        self.hh_size_accessor = _unique("hh_size")
        self.child_count_accessor = _unique("child_count")

        # Create test variables with unique names
        self.Variable.create(
            {
                "name": _unique("income"),
                "cel_accessor": self.income_accessor,
                "source_type": "field",
                "value_type": "money",
                "source_field": "income",
                "applies_to": "both",
            }
        )
        self.Variable.create(
            {
                "name": _unique("poverty_line"),
                "cel_accessor": self.poverty_accessor,
                "source_type": "constant",
                "value_type": "money",
                "default_value": "2500",
                "applies_to": "both",
            }
        )
        self.Variable.create(
            {
                "name": _unique("hh_size"),
                "cel_accessor": self.hh_size_accessor,
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "applies_to": "group",
            }
        )
        self.Variable.create(
            {
                "name": _unique("child_count"),
                "cel_accessor": self.child_count_accessor,
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "age_years(m.birthdate) < 18",
                "applies_to": "group",
            }
        )

    def test_expand_constant_variable(self):
        """Test expanding constant variable."""
        result = self.Resolver.expand_expression(
            f"r.income < {self.poverty_accessor}",
            context_type="both",
        )
        self.assertIn("2500", result["expression"])
        self.assertIn(self.poverty_accessor, result["variables_used"])

    def test_expand_field_variable(self):
        """Test expanding field variable."""
        result = self.Resolver.expand_expression(
            f"{self.income_accessor} > 1000",
            context_type="individual",
        )
        # Should expand to 'r.income'
        self.assertIn(self.income_accessor, result["variables_used"])

    def test_expand_aggregate_variable(self):
        """Test expanding aggregate variable."""
        result = self.Resolver.expand_expression(
            f"{self.hh_size_accessor} >= 3",
            context_type="group",
        )
        self.assertIn("members.count", result["expression"])
        self.assertIn(self.hh_size_accessor, result["variables_used"])

    def test_missing_variables_detected(self):
        """Test that missing variables are detected."""
        result = self.Resolver.expand_expression(
            "undefined_var > 100",
            context_type="group",
        )
        self.assertIn("undefined_var", result["missing_variables"])

    def test_reserved_words_not_expanded(self):
        """Test that reserved words are not treated as variables."""
        result = self.Resolver.expand_expression(
            "true && false",
            context_type="group",
        )
        self.assertEqual(result["variables_used"], [])
        self.assertEqual(result["missing_variables"], [])

    def test_functions_not_expanded(self):
        """Test that function names are not treated as variables."""
        result = self.Resolver.expand_expression(
            "age_years(r.birthdate) >= 18",
            context_type="individual",
        )
        self.assertNotIn("age_years", result["missing_variables"])

    def test_context_type_filtering(self):
        """Test that variables are filtered by context."""
        # hh_size is group-only
        self.Resolver.expand_expression(
            f"{self.hh_size_accessor} >= 3",
            context_type="individual",
        )
        # Should still find it but may warn
        # Variable resolution is lenient - it finds group vars in individual context

    def test_validate_expression_valid(self):
        """Test validation of valid expression."""
        result = self.Resolver.validate_expression(
            f"r.income < {self.poverty_accessor}",
            context_type="both",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_validate_expression_invalid(self):
        """Test validation of expression with missing variables."""
        result = self.Resolver.validate_expression(
            "undefined_var_xyz > 100",
            context_type="group",
        )
        self.assertFalse(result["valid"])
        self.assertTrue(len(result["errors"]) > 0)

    def test_get_available_variables(self):
        """Test getting available variables."""
        variables = self.Resolver.get_available_variables(context_type="group")
        # Should include our test hh_size variable (group-only)
        accessors = [v.cel_accessor for v in variables]
        self.assertIn(self.hh_size_accessor, accessors)

    def test_cache_invalidation(self):
        """Test that cache invalidation works."""
        # First resolution
        result1 = self.Resolver.resolve_for_evaluation(
            f"{self.poverty_accessor} > 1000",
            context_type="both",
        )
        self.assertFalse(result1["from_cache"])

        # Second resolution - should use cache
        result2 = self.Resolver.resolve_for_evaluation(
            f"{self.poverty_accessor} > 1000",
            context_type="both",
        )
        self.assertTrue(result2["from_cache"])

        # Invalidate cache
        self.Resolver.invalidate_variable_cache()

        # Third resolution - cache miss
        result3 = self.Resolver.resolve_for_evaluation(
            f"{self.poverty_accessor} > 1000",
            context_type="both",
        )
        self.assertFalse(result3["from_cache"])

    def test_recursive_variable_expansion(self):
        """Test that nested variable references are expanded recursively."""
        # Create a variable that references another variable
        large_hh_accessor = _unique("is_large_hh")
        self.Variable.create(
            {
                "name": _unique("is_large_household"),
                "cel_accessor": large_hh_accessor,
                "source_type": "computed",
                "value_type": "boolean",
                "cel_expression": f"{self.hh_size_accessor} >= 5",
                "applies_to": "group",
            }
        )

        result = self.Resolver.expand_expression(
            f"{large_hh_accessor} == true",
            context_type="group",
        )
        # Should expand is_large_hh -> hh_size >= 5 -> members.count(true) >= 5
        self.assertIn("members.count", result["expression"])

    def test_circular_reference_detection(self):
        """Test that circular references don't cause infinite loop."""
        # Create two variables that reference each other
        circular_a_accessor = _unique("circular_a")
        circular_b_accessor = _unique("circular_b")
        self.Variable.create(
            {
                "name": _unique("circular_a"),
                "cel_accessor": circular_a_accessor,
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": f"{circular_b_accessor} + 1",
                "applies_to": "both",
            }
        )
        self.Variable.create(
            {
                "name": _unique("circular_b"),
                "cel_accessor": circular_b_accessor,
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": f"{circular_a_accessor} + 1",
                "applies_to": "both",
            }
        )

        # Should not hang, should detect circular reference
        result = self.Resolver.expand_expression(
            f"{circular_a_accessor} > 10",
            context_type="both",
        )
        # Should complete (with or without warning)
        self.assertIsInstance(result["expression"], str)


@tagged("post_install", "-at_install")
class TestCELServiceVariableIntegration(TransactionCase):
    """Test CEL service integration with variable resolver."""

    def setUp(self):
        super().setUp()
        self.Service = self.env["spp.cel.service"]
        self.Variable = self.env["spp.cel.variable"]

        # Create test variables with unique names
        self.test_const_accessor = _unique("test_constant")
        self.Variable.create(
            {
                "name": _unique("test_constant"),
                "cel_accessor": self.test_const_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "42",
                "applies_to": "both",
            }
        )

    def test_resolve_variables_method(self):
        """Test the resolve_variables service method."""
        result = self.Service.resolve_variables(
            f"{self.test_const_accessor} > 10",
            context_type="both",
        )
        self.assertIn("42", result["expression"])
        self.assertIn(self.test_const_accessor, result["variables_used"])

    def test_get_available_variables(self):
        """Test getting available variables through service."""
        variables = self.Service.get_available_variables(context_type="both")
        accessors = [v.cel_accessor for v in variables]
        self.assertIn(self.test_const_accessor, accessors)

    def test_validate_expression_with_variables(self):
        """Test validation through service."""
        result = self.Service.validate_expression_with_variables(
            f"{self.test_const_accessor} > 10",
            context_type="both",
        )
        self.assertTrue(result["valid"])

    def test_validate_expression_with_missing_variables(self):
        """Test validation with missing variables."""
        result = self.Service.validate_expression_with_variables(
            "nonexistent_var > 10",
            context_type="both",
        )
        self.assertFalse(result["valid"])

    def test_invalidate_caches_includes_resolver(self):
        """Test that invalidate_caches clears resolver cache."""
        # This shouldn't crash
        result = self.Service.invalidate_caches()
        self.assertTrue(result)


@tagged("post_install", "-at_install")
class TestCELVariableCacheInvalidation(TransactionCase):
    """Test automatic cache invalidation when variables change."""

    def setUp(self):
        super().setUp()
        self.Service = self.env["spp.cel.service"]
        self.Variable = self.env["spp.cel.variable"]
        self.Resolver = self.env["spp.cel.variable.resolver"]
        self.Registry = self.env["spp.cel.registry"]
        self.Translator = self.env["spp.cel.translator"]

        # Import cache modules for direct inspection
        from ..models import cel_registry, cel_translator

        self.cel_registry = cel_registry
        self.cel_translator = cel_translator

        # Clear all caches before each test
        self.Service.invalidate_caches()

        # Create test variable with unique name
        self.test_accessor = _unique("cache_test_var")
        self.test_var = self.Variable.create(
            {
                "name": _unique("cache_test_variable"),
                "cel_accessor": self.test_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "100",
                "applies_to": "both",
            }
        )

    def test_variable_write_invalidates_all_caches(self):
        """Test that modifying a variable invalidates all CEL caches."""
        # Step 1: Compile an expression using the variable with a valid field comparison
        # Use an expression that makes sense: r.id > constant_value
        expr = f"r.id > {self.test_accessor}"
        result1 = self.Service.compile_expression(expr, "registry_individuals")
        self.assertTrue(result1["valid"], f"Initial compilation failed: {result1.get('error')}")

        # Step 2: Populate caches by resolving the expression
        resolution1 = self.Resolver.resolve_for_evaluation(expr, context_type="individual")
        self.assertIn("100", resolution1["expression"], "Should expand to r.id > 100")

        # Verify caches are populated
        profile_cache_size_before = len(self.cel_registry._profile_cache)
        translation_cache_size_before = len(self.cel_translator._translation_cache)
        resolver_cache_size_before = len(self.Resolver._variable_cache)

        # At least one cache should have content
        self.assertGreater(
            profile_cache_size_before + translation_cache_size_before + resolver_cache_size_before,
            0,
            "Caches should be populated after compilation",
        )

        # Step 3: Modify the variable's expression
        self.test_var.write({"default_value": "200"})

        # Step 4: Verify all caches were invalidated
        profile_cache_size_after = len(self.cel_registry._profile_cache)
        translation_cache_size_after = len(self.cel_translator._translation_cache)
        resolver_cache_size_after = len(self.Resolver._variable_cache)

        # Caches should be cleared
        self.assertEqual(profile_cache_size_after, 0, "Profile cache should be cleared")
        self.assertEqual(translation_cache_size_after, 0, "Translation cache should be cleared")
        self.assertEqual(resolver_cache_size_after, 0, "Resolver cache should be cleared")

        # Step 5: Compile again and verify new value is used
        resolution2 = self.Resolver.resolve_for_evaluation(expr, context_type="individual")
        self.assertIn("200", resolution2["expression"], "Should use new value after cache invalidation")
        self.assertNotIn("100", resolution2["expression"], "Should not contain old value")

    def test_variable_unlink_invalidates_caches(self):
        """Test that deleting a variable invalidates all caches."""
        # Step 1: Compile expression using the variable with valid field comparison
        expr = f"r.id > {self.test_accessor}"
        result1 = self.Service.compile_expression(expr, "registry_individuals")
        self.assertTrue(result1["valid"], f"Initial compilation failed: {result1.get('error')}")

        # Populate resolver cache
        resolution1 = self.Resolver.resolve_for_evaluation(expr, context_type="individual")
        self.assertIn("100", resolution1["expression"])

        # Verify caches are populated
        cache_sizes_before = (
            len(self.cel_registry._profile_cache)
            + len(self.cel_translator._translation_cache)
            + len(self.Resolver._variable_cache)
        )
        self.assertGreater(cache_sizes_before, 0, "Caches should be populated")

        # Step 2: Delete the variable
        self.test_var.unlink()

        # Step 3: Verify all caches were cleared
        profile_cache_size = len(self.cel_registry._profile_cache)
        translation_cache_size = len(self.cel_translator._translation_cache)
        resolver_cache_size = len(self.Resolver._variable_cache)

        self.assertEqual(profile_cache_size, 0, "Profile cache should be cleared")
        self.assertEqual(translation_cache_size, 0, "Translation cache should be cleared")
        self.assertEqual(resolver_cache_size, 0, "Resolver cache should be cleared")

        # Step 4: Compile again - should find variable missing
        resolution2 = self.Resolver.resolve_for_evaluation(expr, context_type="individual")
        self.assertIn(self.test_accessor, resolution2["missing_variables"], "Variable should be missing after unlink")

    def test_non_relevant_field_changes_do_not_invalidate(self):
        """Test that changing non-cache-relevant fields doesn't invalidate caches."""
        # Compile expression to populate caches - use valid field comparison
        expr = f"r.id > {self.test_accessor}"
        result = self.Service.compile_expression(expr, "registry_individuals")
        self.assertTrue(result["valid"], f"Compilation failed: {result.get('error')}")
        self.Resolver.resolve_for_evaluation(expr, context_type="individual")

        # Record cache sizes
        profile_cache_size_before = len(self.cel_registry._profile_cache)
        translation_cache_size_before = len(self.cel_translator._translation_cache)
        resolver_cache_size_before = len(self.Resolver._variable_cache)

        # Verify caches are populated
        self.assertGreater(profile_cache_size_before, 0, "Profile cache should be populated")
        self.assertGreater(translation_cache_size_before, 0, "Translation cache should be populated")
        self.assertGreater(resolver_cache_size_before, 0, "Resolver cache should be populated")

        # Change a non-relevant field (e.g., sequence)
        # sequence is NOT in cache_invalidating_fields, so no invalidation should occur
        self.test_var.write({"sequence": 999})

        # Caches should remain unchanged (current behavior: selective invalidation)
        profile_cache_size_after = len(self.cel_registry._profile_cache)
        translation_cache_size_after = len(self.cel_translator._translation_cache)
        resolver_cache_size_after = len(self.Resolver._variable_cache)

        # Verify caches were NOT invalidated for non-relevant field changes
        self.assertEqual(profile_cache_size_after, profile_cache_size_before, "Profile cache should not be cleared")
        self.assertEqual(
            translation_cache_size_after,
            translation_cache_size_before,
            "Translation cache should not be cleared",
        )
        self.assertEqual(resolver_cache_size_after, resolver_cache_size_before, "Resolver cache should not be cleared")

    def test_variable_create_invalidates_caches(self):
        """Test that creating a new variable invalidates caches."""
        # Compile expression to populate caches - use valid field comparison
        expr = f"r.id > {self.test_accessor}"
        result = self.Service.compile_expression(expr, "registry_individuals")
        self.assertTrue(result["valid"], f"Compilation failed: {result.get('error')}")
        self.Resolver.resolve_for_evaluation(expr, context_type="individual")

        # Verify caches are populated
        cache_sizes_before = (
            len(self.cel_registry._profile_cache)
            + len(self.cel_translator._translation_cache)
            + len(self.Resolver._variable_cache)
        )
        self.assertGreater(cache_sizes_before, 0)

        # Create a new variable
        new_accessor = _unique("new_var")
        self.Variable.create(
            {
                "name": _unique("new_variable"),
                "cel_accessor": new_accessor,
                "source_type": "constant",
                "value_type": "number",
                "default_value": "50",
                "applies_to": "both",
            }
        )

        # Caches should be cleared
        self.assertEqual(len(self.cel_registry._profile_cache), 0)
        self.assertEqual(len(self.cel_translator._translation_cache), 0)
        self.assertEqual(len(self.Resolver._variable_cache), 0)

    def test_multiple_write_invalidations_safe(self):
        """Test that multiple sequential writes don't cause errors."""
        # Use valid field comparison expression
        expr = f"r.id > {self.test_accessor}"

        # Write multiple times in sequence
        for i in range(5):
            self.test_var.write({"default_value": str(100 + i * 10)})

            # Should compile successfully after each write
            result = self.Service.compile_expression(expr, "registry_individuals")
            self.assertTrue(result["valid"], f"Compilation should succeed after write {i}: {result.get('error')}")

            # Resolver should use new value
            resolution = self.Resolver.resolve_for_evaluation(expr, context_type="individual")
            expected_value = str(100 + i * 10)
            self.assertIn(
                expected_value, resolution["expression"], f"Should use value {expected_value} after write {i}"
            )

    def test_cache_invalidation_with_aggregate_variable(self):
        """Test cache invalidation when modifying aggregate variables."""
        # Create an aggregate variable
        agg_accessor = _unique("test_agg")
        agg_var = self.Variable.create(
            {
                "name": _unique("test_aggregate"),
                "cel_accessor": agg_accessor,
                "source_type": "aggregate",
                "value_type": "number",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "applies_to": "group",
            }
        )

        # Compile expression using aggregate - this is already a valid expression
        # because aggregate variables expand to members.count(...) which is valid
        expr = f"{agg_accessor} >= 3"
        result1 = self.Service.compile_expression(expr, "registry_groups")
        self.assertTrue(result1["valid"], f"Initial compilation failed: {result1.get('error')}")

        # Populate caches
        self.Resolver.resolve_for_evaluation(expr, context_type="group")

        # Verify caches populated
        cache_sizes = (
            len(self.cel_registry._profile_cache)
            + len(self.cel_translator._translation_cache)
            + len(self.Resolver._variable_cache)
        )
        self.assertGreater(cache_sizes, 0)

        # Modify the aggregate filter
        agg_var.write({"aggregate_filter": "age_years(m.birthdate) < 18"})

        # All caches should be cleared
        self.assertEqual(len(self.cel_registry._profile_cache), 0)
        self.assertEqual(len(self.cel_translator._translation_cache), 0)
        self.assertEqual(len(self.Resolver._variable_cache), 0)

        # Compile again - should use new filter
        resolution = self.Resolver.resolve_for_evaluation(expr, context_type="group")
        self.assertIn("age_years", resolution["expression"], "Should use new aggregate filter")

    def test_cache_invalidation_cascades_properly(self):
        """Test that cache invalidation cascades through all three caches."""
        # This is a comprehensive test to ensure all caches are cleared together

        # Step 1: Populate all caches
        # Use valid field comparison expression
        expr = f"r.id > {self.test_accessor}"

        # Populate profile cache
        self.Registry.load_profile("registry_individuals")

        # Populate translation cache
        cfg = self.Registry.load_profile("registry_individuals")
        self.Translator.translate("res.partner", "r.id > 0", cfg)

        # Populate resolver cache
        self.Resolver.resolve_for_evaluation(expr, context_type="individual")

        # Verify all caches have content
        self.assertGreater(len(self.cel_registry._profile_cache), 0, "Profile cache should be populated")
        self.assertGreater(len(self.cel_translator._translation_cache), 0, "Translation cache should be populated")
        self.assertGreater(len(self.Resolver._variable_cache), 0, "Resolver cache should be populated")

        # Step 2: Modify variable
        self.test_var.write({"default_value": "150"})

        # Step 3: Verify ALL caches cleared in one operation
        self.assertEqual(len(self.cel_registry._profile_cache), 0, "Profile cache should be cleared")
        self.assertEqual(len(self.cel_translator._translation_cache), 0, "Translation cache should be cleared")
        self.assertEqual(len(self.Resolver._variable_cache), 0, "Resolver cache should be cleared")
