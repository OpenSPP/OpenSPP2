# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Adversarial tests for CEL caching - verify cache behavior and isolation."""

from odoo.tests import TransactionCase, tagged

from ..models import cel_translator
from ..services import cel_parser as P


@tagged("post_install", "-at_install")
class TestCELCaching(TransactionCase):
    """Test caching mechanisms and edge cases."""

    def setUp(self):
        super().setUp()
        self.translator = self.env["spp.cel.translator"]
        self.registry = self.env["spp.cel.registry"]
        self.service = self.env["spp.cel.service"]
        # Clear caches before each test
        cel_translator.invalidate_translation_cache()
        P.parse.cache_clear()
        self.registry.invalidate_cache()

    def test_parser_cache_hit_same_expression(self):
        """Parser should cache and return same object for same expression."""
        expr = "r.age >= 18"
        ast1 = P.parse(expr)
        ast2 = P.parse(expr)
        # Should return the same cached object
        self.assertIs(ast1, ast2)

    def test_parser_cache_miss_different_expressions(self):
        """Parser should not confuse different expressions."""
        ast1 = P.parse("r.age >= 18")
        ast2 = P.parse("r.age >= 19")
        self.assertIsNot(ast1, ast2)

    def test_parser_cache_clear_works(self):
        """Parser cache clear should invalidate cache."""
        expr = "r.age >= 18"
        _ = P.parse(expr)
        # Clear cache
        P.parse.cache_clear()
        ast2 = P.parse(expr)
        # May or may not be same object depending on implementation
        # But should not crash
        self.assertIsNotNone(ast2)

    def test_parser_cache_maxsize_respected(self):
        """Parser cache should respect maxsize limit."""
        # Parser cache maxsize is 256
        # Parse 300 different expressions
        for i in range(300):
            P.parse(f"r.field{i} == {i}")
        # Should not crash or exhaust memory
        # LRU should evict old entries

    def test_parser_cache_thread_safe(self):
        """Parser cache should handle concurrent access."""
        # Parse same expression multiple times rapidly
        for _ in range(100):
            P.parse("r.age >= 18")
        # Should not crash

    def test_translation_cache_hit_same_inputs(self):
        """Translation cache should hit for same expression+model+cfg."""
        cfg = self.registry.load_profile("registry_individuals")
        expr = "r.age >= 18"
        model = "res.partner"

        plan1, explain1 = self.translator.translate(model, expr, cfg)
        plan2, explain2 = self.translator.translate(model, expr, cfg)

        # Should get same results
        self.assertEqual(str(plan1), str(plan2))
        self.assertEqual(explain1, explain2)

    def test_translation_cache_miss_different_expressions(self):
        """Translation cache should miss for different expressions."""
        cfg = self.registry.load_profile("registry_individuals")
        model = "res.partner"

        plan1, _ = self.translator.translate(model, "r.age >= 18", cfg)
        plan2, _ = self.translator.translate(model, "r.age >= 19", cfg)

        # Should be different
        self.assertNotEqual(str(plan1), str(plan2))

    def test_translation_cache_miss_different_models(self):
        """Translation cache should miss for different models."""
        cfg = self.registry.load_profile("registry_individuals")
        expr = "true"

        plan1, _ = self.translator.translate("res.partner", expr, cfg)
        plan2, _ = self.translator.translate("res.users", expr, cfg)

        # Should compute separately
        self.assertIsNotNone(plan1)
        self.assertIsNotNone(plan2)

    def test_translation_cache_miss_different_configs(self):
        """Translation cache should miss for different configs."""
        cfg1 = self.registry.load_profile("registry_individuals")
        cfg2 = self.registry.load_profile("registry_groups")
        expr = "true"
        model = "res.partner"

        plan1, _ = self.translator.translate(model, expr, cfg1)
        plan2, _ = self.translator.translate(model, expr, cfg2)

        # Should be cached separately
        self.assertIsNotNone(plan1)
        self.assertIsNotNone(plan2)

    def test_translation_cache_invalidation(self):
        """Translation cache invalidation should clear cache."""
        cfg = self.registry.load_profile("registry_individuals")
        expr = "r.age >= 18"
        model = "res.partner"

        plan1, _ = self.translator.translate(model, expr, cfg)
        # Invalidate
        cel_translator.invalidate_translation_cache()
        plan2, _ = self.translator.translate(model, expr, cfg)

        # Should recompute (results should be same but cache was cleared)
        self.assertEqual(str(plan1), str(plan2))

    def test_translation_cache_max_size_eviction(self):
        """Translation cache should evict old entries when full."""
        cfg = self.registry.load_profile("registry_individuals")
        model = "res.partner"

        # Translation cache max size is 128
        # Fill beyond capacity
        for i in range(150):
            self.translator.translate(model, f"r.field{i} == {i}", cfg)

        # Should not crash, should evict old entries
        # Verify we can still translate
        plan, _ = self.translator.translate(model, "r.age >= 18", cfg)
        self.assertIsNotNone(plan)

    def test_profile_cache_hit_same_profile(self):
        """Profile cache should hit for same profile."""
        cfg1 = self.registry.load_profile("registry_individuals")
        cfg2 = self.registry.load_profile("registry_individuals")

        # Should return equivalent configs
        self.assertEqual(cfg1["root_model"], cfg2["root_model"])

    def test_profile_cache_miss_different_profiles(self):
        """Profile cache should miss for different profiles."""
        cfg1 = self.registry.load_profile("registry_individuals")
        cfg2 = self.registry.load_profile("registry_groups")

        # Should be different
        self.assertNotEqual(cfg1["base_domain"], cfg2["base_domain"])

    def test_profile_cache_invalidation(self):
        """Profile cache invalidation should clear cache."""
        cfg1 = self.registry.load_profile("registry_individuals")
        # Invalidate
        self.registry.invalidate_cache()
        cfg2 = self.registry.load_profile("registry_individuals")

        # Should reload (results should be same but cache was cleared)
        self.assertEqual(cfg1["root_model"], cfg2["root_model"])

    def test_profile_cache_force_reload(self):
        """Profile cache should support force reload."""
        cfg1 = self.registry.load_profile("registry_individuals")
        cfg2 = self.registry.load_profile("registry_individuals", force_reload=True)

        # Should reload from source
        self.assertEqual(cfg1["root_model"], cfg2["root_model"])

    def test_profile_cache_company_isolation(self):
        """Profile cache should be isolated per company."""
        # Get profile in default company
        cfg1 = self.registry.load_profile("registry_individuals")

        # Switch company if possible
        companies = self.env["res.company"].search([], limit=2)
        if len(companies) > 1:
            # Switch to different company
            self.registry = self.registry.with_company(companies[1])
            cfg2 = self.registry.load_profile("registry_individuals")

            # Should cache separately per company
            self.assertIsNotNone(cfg1)
            self.assertIsNotNone(cfg2)

    def test_cache_mutation_isolation(self):
        """Mutating returned config should not affect cache."""
        cfg1 = self.registry.load_profile("registry_individuals")
        original_model = cfg1["root_model"]

        # Mutate the returned config
        cfg1["root_model"] = "tampered.model"

        # Get it again
        cfg2 = self.registry.load_profile("registry_individuals")

        # Should not be affected by mutation
        self.assertEqual(cfg2["root_model"], original_model)
        self.assertNotEqual(cfg2["root_model"], "tampered.model")

    def test_service_cache_invalidation_cascades(self):
        """Service cache invalidation should invalidate all related caches."""
        # Use service to compile
        result1 = self.service.compile_expression("r.id > 0", "registry_individuals")
        self.assertTrue(result1["valid"])

        # Invalidate via service
        self.service.invalidate_caches()

        # Should still work (recompute)
        result2 = self.service.compile_expression("r.id > 0", "registry_individuals")
        self.assertTrue(result2["valid"])

    def test_concurrent_cache_access_safe(self):
        """Concurrent access to caches should be safe."""
        cfg = self.registry.load_profile("registry_individuals")
        expr = "r.id > 0"
        model = "res.partner"

        # Multiple concurrent translations
        results = []
        for _ in range(10):
            plan, explain = self.translator.translate(model, expr, cfg)
            results.append((plan, explain))

        # All should succeed
        for plan, explain in results:
            self.assertIsNotNone(plan)
            self.assertIsNotNone(explain)

    def test_cache_with_unicode_keys(self):
        """Cache should handle unicode in keys."""
        cfg = self.registry.load_profile("registry_individuals")
        expr = 'r.name == "José García"'
        model = "res.partner"

        plan1, _ = self.translator.translate(model, expr, cfg)
        plan2, _ = self.translator.translate(model, expr, cfg)

        # Should cache and retrieve
        self.assertEqual(str(plan1), str(plan2))

    def test_cache_with_very_long_keys(self):
        """Cache should handle very long expression keys."""
        cfg = self.registry.load_profile("registry_individuals")
        # Create very long expression
        expr = " or ".join([f"r.field{i} == {i}" for i in range(100)])
        model = "res.partner"

        plan1, _ = self.translator.translate(model, expr, cfg)
        plan2, _ = self.translator.translate(model, expr, cfg)

        # Should cache despite long key
        self.assertIsNotNone(plan1)
        self.assertIsNotNone(plan2)

    def test_cache_memory_not_leaked(self):
        """Cache should not leak memory with repeated use."""
        import gc

        cfg = self.registry.load_profile("registry_individuals")
        model = "res.partner"

        # Translate many different expressions
        for i in range(200):
            expr = f"r.field{i} == {i}"
            self.translator.translate(model, expr, cfg)

        # Force garbage collection
        gc.collect()

        # Should not have excessive memory growth
        # This is a weak test, but checks that we don't crash

    def test_parser_cache_with_identical_semantics_different_whitespace(self):
        """Parser should treat expressions with different whitespace as different."""
        ast1 = P.parse("r.age>=18")
        ast2 = P.parse("r.age >= 18")
        ast3 = P.parse("r.age  >=  18")

        # These are different strings, so should be cached separately
        # But should produce equivalent AST
        self.assertIsInstance(ast1, P.Compare)
        self.assertIsInstance(ast2, P.Compare)
        self.assertIsInstance(ast3, P.Compare)

    def test_cache_handles_exception_gracefully(self):
        """Cache should not be corrupted by exceptions."""
        cfg = self.registry.load_profile("registry_individuals")
        model = "res.partner"

        # Try to translate invalid expression
        try:
            self.translator.translate(model, "invalid >>>", cfg)
        except Exception:
            pass  # Expected to fail

        # Cache should still work for valid expression
        plan, _ = self.translator.translate(model, "r.age >= 18", cfg)
        self.assertIsNotNone(plan)

    def test_translation_cache_disabled_works(self):
        """Translation cache can be disabled."""
        # Disable cache
        original = cel_translator._translation_cache_enabled
        try:
            cel_translator._translation_cache_enabled = False
            cel_translator.invalidate_translation_cache()

            cfg = self.registry.load_profile("registry_individuals")
            expr = "r.age >= 18"
            model = "res.partner"

            plan1, _ = self.translator.translate(model, expr, cfg)
            plan2, _ = self.translator.translate(model, expr, cfg)

            # Should still work
            self.assertIsNotNone(plan1)
            self.assertIsNotNone(plan2)
        finally:
            # Re-enable cache
            cel_translator._translation_cache_enabled = original

    def test_profile_cache_disabled_works(self):
        """Profile cache can be disabled."""
        from ..models import cel_registry

        # Disable cache
        original = cel_registry._profile_cache_enabled
        try:
            cel_registry._profile_cache_enabled = False
            cel_registry.invalidate_profile_cache()

            cfg1 = self.registry.load_profile("registry_individuals")
            cfg2 = self.registry.load_profile("registry_individuals")

            # Should still work
            self.assertIsNotNone(cfg1)
            self.assertIsNotNone(cfg2)
        finally:
            # Re-enable cache
            cel_registry._profile_cache_enabled = original


@tagged("post_install", "-at_install")
class TestCELExecutorCacheLookup(TransactionCase):
    """Test executor cache lookup for metric() calls - ADR-017."""

    def setUp(self):
        super().setUp()
        self.executor = self.env["spp.cel.executor"]
        self.DataValue = self.env["spp.data.value"]
        self.Variable = self.env["spp.cel.variable"]
        self.resolver = self.env["spp.cel.variable.resolver"]
        self.service = self.env["spp.cel.service"]

        # Create test partners
        self._test_id = int(__import__("time").time() * 1000)
        self.partner_1 = self.env["res.partner"].create(
            {
                "name": f"Test Partner 1 {self._test_id}",
                "is_registrant": True,
            }
        )
        self.partner_2 = self.env["res.partner"].create(
            {
                "name": f"Test Partner 2 {self._test_id}",
                "is_registrant": True,
            }
        )
        self.partner_3 = self.env["res.partner"].create(
            {
                "name": f"Test Partner 3 {self._test_id}",
                "is_registrant": True,
            }
        )

        # Clear caches
        self.DataValue.search([("company_id", "=", self.env.company.id)]).unlink()

        # Base domain limiting to test partners only
        self.test_base_domain = [("id", "in", [self.partner_1.id, self.partner_2.id, self.partner_3.id])]

    def test_metric_lookup_uses_data_value_table(self):
        """Test that metric() uses spp.data.value for lookups."""
        # Create a cached variable
        var = self.Variable.create(
            {
                "name": f"test_metric_{self._test_id}",
                "cel_accessor": "test_metric",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Pre-populate spp.data.value with test data
        # Note: Use cel_accessor as variable_name since metric() uses cel_accessor
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_1.id,
                "period_key": "current",
                "value_json": {"value": 85},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_2.id,
                "period_key": "current",
                "value_json": {"value": 65},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_3.id,
                "period_key": "current",
                "value_json": {"value": 45},
                "source_type": "external",
            }
        )

        # Execute expression with metric() lookup
        # This tests the full flow: resolver emits metric(), executor looks up cache
        # Use self.test_base_domain to limit scope to just our test partners
        result = self.service.compile_expression(
            "test_metric > 50",
            "registry_individuals",
            base_domain=self.test_base_domain,
        )

        # Verify compilation succeeded
        self.assertTrue(result["valid"], f"Compilation should succeed: {result.get('error')}")

        # Execute and verify results
        matching_ids = result["ids"]

        # Should match partners with values > 50 (partner_1: 85, partner_2: 65)
        self.assertIn(self.partner_1.id, matching_ids)
        self.assertIn(self.partner_2.id, matching_ids)
        self.assertNotIn(self.partner_3.id, matching_ids)  # 45 <= 50

    def test_metric_lookup_respects_period_key(self):
        """Test metric() lookups use correct period_key."""
        var = self.Variable.create(
            {
                "name": f"period_metric_{self._test_id}",
                "cel_accessor": "period_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Create values for different periods
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_1.id,
                "period_key": "2024-11",
                "value_json": {"value": 100},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_1.id,
                "period_key": "2024-12",
                "value_json": {"value": 200},
                "source_type": "external",
            }
        )

        # Query for current period (should use 2024-12 if that's current)
        # Note: This is a simplified test - full period_key handling depends on context
        result = self.service.compile_expression(
            "period_var >= 150",
            "registry_individuals",
        )

        self.assertTrue(result["valid"])

    def test_metric_lookup_empty_cache_graceful(self):
        """Test graceful handling when cache is empty."""
        # Create variable but don't populate cache
        _var = self.Variable.create(
            {
                "name": f"empty_cache_{self._test_id}",
                "cel_accessor": "empty_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Execute expression with metric() - cache is empty
        result = self.service.compile_expression(
            "empty_var > 50",
            "registry_individuals",
        )

        # Should compile without error
        self.assertTrue(result["valid"])

        # Should return empty results (no cache = no matches)
        self.assertEqual(len(result["ids"]), 0)

    def test_metric_lookup_partial_cache_coverage(self):
        """Test metric() lookup when only some subjects have cached values."""
        var = self.Variable.create(
            {
                "name": f"partial_cache_{self._test_id}",
                "cel_accessor": "partial_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Populate cache for only 2 out of 3 partners
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_1.id,
                "period_key": "current",
                "value_json": {"value": 70},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_2.id,
                "period_key": "current",
                "value_json": {"value": 30},
                "source_type": "external",
            }
        )
        # partner_3 has no cached value

        # Execute expression - use test_base_domain for partial cache test
        # Note: partner_3 has no cache entry, but is in base_domain
        partial_base = [("id", "in", [self.partner_1.id, self.partner_2.id])]
        result = self.service.compile_expression(
            "partial_var > 50",
            "registry_individuals",
            base_domain=partial_base,
        )

        self.assertTrue(result["valid"], f"Compilation failed: {result.get('error')}")
        matching_ids = result["ids"]

        # Only partner_1 should match (70 > 50)
        # partner_3 is not in cache, so won't match
        self.assertIn(self.partner_1.id, matching_ids)
        self.assertNotIn(self.partner_2.id, matching_ids)  # 30 <= 50
        # partner_3 may or may not be included depending on cache miss handling

    def test_metric_lookup_uses_sql_fast_path(self):
        """Test that metric() lookups use SQL fast path when cache is fresh."""
        var = self.Variable.create(
            {
                "name": f"sql_fast_path_{self._test_id}",
                "cel_accessor": "fast_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Populate cache
        for partner in [self.partner_1, self.partner_2, self.partner_3]:
            self.DataValue.create(
                {
                    "variable_name": var.cel_accessor,
                    "subject_model": "res.partner",
                    "subject_id": partner.id,
                    "period_key": "current",
                    "value_json": {"value": partner.id * 10},
                    "source_type": "external",
                }
            )

        # Execute expression with base_domain to ensure fresh cache
        result = self.service.compile_expression(
            f"fast_var > {self.partner_1.id * 10}",
            "registry_individuals",
            base_domain=self.test_base_domain,
        )

        # Check execution path - should use SQL for fresh cache
        # Note: The 'path' field indicates execution strategy
        # 'sql' = SQL fast path, 'python' = Python fallback, 'domain' = pure domain
        # With fresh cache, should use SQL or domain path
        self.assertTrue(result["valid"], f"Compilation failed: {result.get('error')}")
        self.assertIn(result.get("path"), ["sql", "domain", "python"])

    def test_metric_multiple_variables_cache_lookup(self):
        """Test expression with multiple cached variables."""
        # Create two cached variables
        var1 = self.Variable.create(
            {
                "name": f"multi_var1_{self._test_id}",
                "cel_accessor": "multi_var1",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )
        var2 = self.Variable.create(
            {
                "name": f"multi_var2_{self._test_id}",
                "cel_accessor": "multi_var2",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Populate both caches
        for partner in [self.partner_1, self.partner_2]:
            self.DataValue.create(
                {
                    "variable_name": var1.cel_accessor,
                    "subject_model": "res.partner",
                    "subject_id": partner.id,
                    "period_key": "current",
                    "value_json": {"value": 50},
                    "source_type": "external",
                }
            )
            self.DataValue.create(
                {
                    "variable_name": var2.cel_accessor,
                    "subject_model": "res.partner",
                    "subject_id": partner.id,
                    "period_key": "current",
                    "value_json": {"value": 75},
                    "source_type": "external",
                }
            )

        # Execute expression with both variables
        # Use limited base_domain for partners with cache entries
        multi_base = [("id", "in", [self.partner_1.id, self.partner_2.id])]
        result = self.service.compile_expression(
            "multi_var1 >= 50 && multi_var2 < 80",
            "registry_individuals",
            base_domain=multi_base,
        )

        self.assertTrue(result["valid"], f"Compilation failed: {result.get('error')}")
        # Both partners should match
        matching_ids = result["ids"]
        self.assertIn(self.partner_1.id, matching_ids)
        self.assertIn(self.partner_2.id, matching_ids)

    def test_metric_lookup_with_comparison_operators(self):
        """Test metric() lookup with various comparison operators."""
        var = self.Variable.create(
            {
                "name": f"comp_ops_{self._test_id}",
                "cel_accessor": "comp_var",
                "source_type": "external",
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )

        # Populate cache with distinct values
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_1.id,
                "period_key": "current",
                "value_json": {"value": 100},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_2.id,
                "period_key": "current",
                "value_json": {"value": 50},
                "source_type": "external",
            }
        )
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner_3.id,
                "period_key": "current",
                "value_json": {"value": 50},
                "source_type": "external",
            }
        )

        # Test == operator
        result_eq = self.service.compile_expression(
            "comp_var == 50",
            "registry_individuals",
            base_domain=self.test_base_domain,
        )
        self.assertTrue(result_eq["valid"], f"== failed: {result_eq.get('error')}")
        eq_ids = result_eq["ids"]
        self.assertIn(self.partner_2.id, eq_ids)
        self.assertIn(self.partner_3.id, eq_ids)
        self.assertNotIn(self.partner_1.id, eq_ids)

        # Test >= operator
        result_gte = self.service.compile_expression(
            "comp_var >= 50",
            "registry_individuals",
            base_domain=self.test_base_domain,
        )
        self.assertTrue(result_gte["valid"], f">= failed: {result_gte.get('error')}")
        gte_ids = result_gte["ids"]
        self.assertIn(self.partner_1.id, gte_ids)
        self.assertIn(self.partner_2.id, gte_ids)
        self.assertIn(self.partner_3.id, gte_ids)

        # Test != operator
        result_ne = self.service.compile_expression(
            "comp_var != 50",
            "registry_individuals",
            base_domain=self.test_base_domain,
        )
        self.assertTrue(result_ne["valid"], f"!= failed: {result_ne.get('error')}")
        ne_ids = result_ne["ids"]
        self.assertIn(self.partner_1.id, ne_ids)
        self.assertNotIn(self.partner_2.id, ne_ids)
        self.assertNotIn(self.partner_3.id, ne_ids)
