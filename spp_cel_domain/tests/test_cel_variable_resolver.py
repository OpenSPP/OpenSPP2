# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL Variable Resolver - ADR-017 Cache Strategy Detection.

Tests cover:
- Detection of cached variables (cache_strategy='ttl' or 'manual')
- Emission of metric() calls for cached variables
- Inline expansion for non-cached variables (cache_strategy='none')
- Cache strategy analysis
"""

import time

from odoo.tests import TransactionCase, tagged

from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestCELVariableResolverCaching(TransactionCase, CELTestDataMixin):
    """Test variable resolver cache strategy detection (ADR-017)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.resolver = cls.env["spp.cel.variable.resolver"]
        cls.Variable = cls.env["spp.cel.variable"]

    def setUp(self):
        super().setUp()
        # Invalidate cache before each test
        self.resolver.invalidate_variable_cache()

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE STRATEGY DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_expand_cached_variable_emits_metric_ttl(self):
        """Variables with cache_strategy='ttl' should emit metric() call."""
        # Create a cached variable
        _var = self.Variable.create(
            {
                "name": f"cached_score_{self._test_id}",
                "cel_accessor": "cached_score",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.score * 2",
                "cache_strategy": "ttl",
                "cache_ttl_seconds": 3600,
            }
        )

        # Expand expression referencing the variable
        result = self.resolver.expand_expression(
            "cached_score > 50",
            context_type="individual",
        )

        # Assert metric() call was emitted
        self.assertIn("metric('cached_score', me)", result["expression"])
        self.assertIn("cached_score", result["variables_used"])

        # Should NOT contain the original CEL expression
        self.assertNotIn("r.score * 2", result["expression"])

    def test_expand_cached_variable_emits_metric_manual(self):
        """Variables with cache_strategy='manual' should emit metric() call."""
        # Create a manually cached variable
        _var = self.Variable.create(
            {
                "name": f"manual_var_{self._test_id}",
                "cel_accessor": "manual_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "manual",
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            "manual_var == 100",
            context_type="individual",
        )

        # Assert metric() call was emitted
        self.assertIn("metric('manual_var', me)", result["expression"])
        self.assertIn("manual_var", result["variables_used"])

    def test_expand_inline_variable_expands_cel_none_strategy(self):
        """Variables with cache_strategy='none' should expand to inline CEL."""
        # Create a non-cached variable
        _var = self.Variable.create(
            {
                "name": f"inline_var_{self._test_id}",
                "cel_accessor": "inline_var",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.income / 1000",
                "cache_strategy": "none",
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            "inline_var > 5",
            context_type="individual",
        )

        # Assert CEL expression was expanded inline
        self.assertIn("r.income / 1000", result["expression"])
        self.assertIn("inline_var", result["variables_used"])

        # Should NOT emit metric() call
        self.assertNotIn("metric(", result["expression"])

    def test_expand_inline_variable_expands_cel_session_strategy(self):
        """Variables with cache_strategy='session' should expand to inline CEL."""
        # Create a session-cached variable
        # Note: We use r.custom_field to avoid expansion of existing 'age' variable
        _var = self.Variable.create(
            {
                "name": f"session_var_{self._test_id}",
                "cel_accessor": f"session_var_{self._test_id}",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.custom_months * 12",
                "cache_strategy": "session",
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            f"session_var_{self._test_id} >= 180",
            context_type="individual",
        )

        # Assert CEL expression was expanded inline (session != persistent cache)
        self.assertIn("r.custom_months * 12", result["expression"])

        # Should NOT emit metric() call (session cache is in-memory, not spp.data.value)
        self.assertNotIn("metric(", result["expression"])

    def test_expand_mixed_cached_and_inline_variables(self):
        """Test expression with both cached and inline variables."""
        # Create cached variable with unique accessor to avoid conflict with system vars
        _cached_var = self.Variable.create(
            {
                "name": f"mixed_cached_{self._test_id}",
                "cel_accessor": f"mixed_cached_{self._test_id}",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Create inline variable with unique accessor
        _inline_var = self.Variable.create(
            {
                "name": f"mixed_inline_{self._test_id}",
                "cel_accessor": f"mixed_inline_{self._test_id}",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "members.count(true)",
                "cache_strategy": "none",
            }
        )

        # Expand expression with both
        result = self.resolver.expand_expression(
            f"mixed_cached_{self._test_id} < 50 && mixed_inline_{self._test_id} > 3",
            context_type="group",
        )

        # Assert cached variable uses metric()
        self.assertIn(f"metric('mixed_cached_{self._test_id}', me)", result["expression"])

        # Assert inline variable is expanded
        self.assertIn("members.count(true)", result["expression"])

        # Both should be in variables_used
        self.assertIn(f"mixed_cached_{self._test_id}", result["variables_used"])
        self.assertIn(f"mixed_inline_{self._test_id}", result["variables_used"])

    def test_expand_nested_cached_variables(self):
        """Test that nested cached variables emit metric() calls."""
        # Create base cached variable
        _base_var = self.Variable.create(
            {
                "name": f"base_score_{self._test_id}",
                "cel_accessor": "base_score",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Create derived cached variable referencing base
        _derived_var = self.Variable.create(
            {
                "name": f"derived_score_{self._test_id}",
                "cel_accessor": "derived_score",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "base_score * 2",
                "cache_strategy": "ttl",
            }
        )

        # Expand expression with derived variable
        result = self.resolver.expand_expression(
            "derived_score > 100",
            context_type="individual",
        )

        # Derived variable should emit its own metric() call
        self.assertIn("metric('derived_score', me)", result["expression"])

        # Should NOT expand to base_score (derived is cached independently)
        self.assertNotIn("base_score", result["expression"])

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE INFO ANALYSIS TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_analyze_expression_caching(self):
        """Test analysis of which variables are cached vs inline."""
        # Create test variables
        _cached_var = self.Variable.create(
            {
                "name": f"cached_{self._test_id}",
                "cel_accessor": "cached_test",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        _inline_var = self.Variable.create(
            {
                "name": f"inline_{self._test_id}",
                "cel_accessor": "inline_test",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.value",
                "cache_strategy": "none",
            }
        )

        _session_var = self.Variable.create(
            {
                "name": f"session_{self._test_id}",
                "cel_accessor": "session_test",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.other",
                "cache_strategy": "session",
            }
        )

        # Analyze expression
        cache_info = self.resolver.analyze_expression_caching(
            "cached_test > 10 && inline_test < 5 && session_test == 3",
            context_type="individual",
        )

        # Verify classification
        self.assertIn("cached_test", cache_info["cached_variables"])
        self.assertIn("inline_test", cache_info["inline_variables"])
        self.assertIn("session_test", cache_info["session_cached_variables"])

        # Verify details
        self.assertIn("cached_test", cache_info["variable_details"])
        self.assertEqual(cache_info["variable_details"]["cached_test"]["cache_strategy"], "ttl")

    def test_resolve_with_cache_info(self):
        """Test resolve_with_cache_info provides both expansion and cache metadata."""
        # Create cached variable
        _var = self.Variable.create(
            {
                "name": f"cache_info_test_{self._test_id}",
                "cel_accessor": "cache_info_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Resolve with cache info
        result = self.resolver.resolve_with_cache_info(
            "cache_info_var >= 75",
            context_type="individual",
        )

        # Should have expanded expression
        self.assertIn("metric('cache_info_var', me)", result["expression"])

        # Should have cache info
        self.assertIn("cache_info", result)
        self.assertIn("cache_info_var", result["cache_info"]["cached_variables"])

        # Should indicate cache join required
        self.assertTrue(result["requires_cache_join"])

    def test_resolve_with_cache_info_no_cached_vars(self):
        """Test resolve_with_cache_info when no cached variables are present."""
        # Create only inline variables
        _var = self.Variable.create(
            {
                "name": f"no_cache_{self._test_id}",
                "cel_accessor": "no_cache_var",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.value",
                "cache_strategy": "none",
            }
        )

        # Resolve with cache info
        result = self.resolver.resolve_with_cache_info(
            "no_cache_var > 10",
            context_type="individual",
        )

        # Should NOT require cache join
        self.assertFalse(result["requires_cache_join"])
        self.assertEqual(len(result["cache_info"]["cached_variables"]), 0)

    # ═══════════════════════════════════════════════════════════════════════
    # EDGE CASES
    # ═══════════════════════════════════════════════════════════════════════

    def test_expand_constant_cached_variable(self):
        """Test that cached constant variables emit metric() calls."""
        # Create cached constant with unique accessor to avoid conflict with system var
        _var = self.Variable.create(
            {
                "name": f"cached_constant_{self._test_id}",
                "cel_accessor": f"cached_const_{self._test_id}",
                "source_type": "constant",
                "value_type": "money",
                "default_value": "2500",
                "cache_strategy": "ttl",  # Even constants can be cached
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            f"r.income < cached_const_{self._test_id}",
            context_type="individual",
        )

        # Should emit metric() call, not inline constant
        self.assertIn(f"metric('cached_const_{self._test_id}', me)", result["expression"])
        self.assertNotIn("2500", result["expression"])

    def test_expand_field_cached_variable(self):
        """Test that cached field variables emit metric() calls."""
        # Create cached field variable
        _var = self.Variable.create(
            {
                "name": f"cached_field_{self._test_id}",
                "cel_accessor": "age_cached",
                "source_type": "field",
                "value_type": "number",
                "source_model": "res.partner",
                "source_field": "age",
                "cache_strategy": "ttl",
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            "age_cached >= 18",
            context_type="individual",
        )

        # Should emit metric() call, not field access
        self.assertIn("metric('age_cached', me)", result["expression"])
        self.assertNotIn("r.age", result["expression"])

    def test_expand_variable_default_cache_strategy(self):
        """Test variable with no explicit cache_strategy defaults to 'none'."""
        # Create variable without cache_strategy (should default to 'none')
        _var = self.Variable.create(
            {
                "name": f"default_strategy_{self._test_id}",
                "cel_accessor": "default_var",
                "source_type": "computed",
                "value_type": "number",
                "cel_expression": "r.value * 3",
                # No cache_strategy specified
            }
        )

        # Expand expression
        result = self.resolver.expand_expression(
            "default_var > 30",
            context_type="individual",
        )

        # Should expand inline (default is 'none')
        self.assertIn("r.value * 3", result["expression"])
        self.assertNotIn("metric(", result["expression"])

    def test_cache_strategy_logging(self):
        """Test that cache strategy detection is logged for debugging."""
        # This test verifies logging behavior (check logs manually or with log capture)
        import logging

        # Create cached variable
        _var = self.Variable.create(
            {
                "name": f"log_test_{self._test_id}",
                "cel_accessor": "log_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "manual",
            }
        )

        # Expand with logging enabled
        with self.assertLogs("odoo.addons.spp_cel_domain.models.cel_variable_resolver", level=logging.DEBUG) as log_ctx:
            self.resolver.expand_expression(
                "log_var == 42",
                context_type="individual",
            )

        # Verify log message about cache strategy
        self.assertTrue(
            any("cache_strategy='manual'" in msg for msg in log_ctx.output),
            "Expected debug log about cache strategy detection",
        )
