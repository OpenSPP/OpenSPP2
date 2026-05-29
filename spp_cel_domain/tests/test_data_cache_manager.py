# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Data Cache Manager - ADR-017 Variable Caching Strategy.

Tests cover:
- Pre-computation of cached variables
- Cache invalidation
- Session cache management
- Batch pre-computation for all cached variables
- Integration with spp.data.value cache table
- External-value dispatch hooks on spp.data.provider
"""

import time
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..models.cel_queryplan import MetricCompare
from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestDataCacheManager(TransactionCase, CELTestDataMixin):
    """Test spp.data.cache.manager model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.cache_mgr = cls.env["spp.data.cache.manager"]
        cls.DataValue = cls.env["spp.data.value"]
        cls.Variable = cls.env["spp.cel.variable"]

        # Create test partners (beneficiaries)
        cls.partner_1 = cls.env["res.partner"].create(
            {
                "name": f"Test Partner 1 {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.partner_2 = cls.env["res.partner"].create(
            {
                "name": f"Test Partner 2 {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.partner_3 = cls.env["res.partner"].create(
            {
                "name": f"Test Partner 3 {cls._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.test_partners = cls.partner_1 + cls.partner_2 + cls.partner_3

    def setUp(self):
        super().setUp()
        # Clear cache before each test
        self.DataValue.search([("company_id", "=", self.env.company.id)]).unlink()
        self.cache_mgr.clear_session_cache()

    # ═══════════════════════════════════════════════════════════════════════
    # PRE-COMPUTATION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_precompute_variable_ttl_strategy(self):
        """Test pre-computation stores values in spp.data.value for TTL cached variables."""
        # Create a cached variable with ttl strategy
        var = self.Variable.create(
            {
                "name": f"test_score_{self._test_id}",
                "cel_accessor": f"test_score_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "100",
                "cache_strategy": "ttl",
                "cache_ttl_seconds": 3600,
            }
        )

        # Pre-compute the variable
        result = self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
            period_key="current",
        )

        # Assert pre-computation succeeded
        self.assertTrue(result["success"])
        self.assertEqual(result["computed"], 3)
        self.assertEqual(result["cached"], 3)
        self.assertEqual(result["errors"], 0)

        # Verify values exist in spp.data.value
        cached_values = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
                ("subject_id", "in", self.test_partners.ids),
                ("period_key", "=", "current"),
            ]
        )

        self.assertEqual(len(cached_values), 3)
        for cv in cached_values:
            self.assertEqual(cv.value_json.get("value"), 100)
            # source_type is mapped from 'constant' to 'computed' for cache storage
            self.assertEqual(cv.source_type, "computed")

    def test_precompute_variable_manual_strategy(self):
        """Test pre-computation works for manual cache strategy."""
        # Create a cached variable with manual strategy and monthly granularity
        var = self.Variable.create(
            {
                "name": f"manual_var_{self._test_id}",
                "cel_accessor": f"manual_var_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "50",
                "cache_strategy": "manual",
                "period_granularity": "monthly",  # Required for period_key to work
            }
        )

        # Pre-compute the variable
        result = self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
            period_key="2024-12",
        )

        # Assert success
        self.assertTrue(result["success"])
        self.assertEqual(result["computed"], 3)

        # Verify values exist in spp.data.value
        cached_values = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
                ("period_key", "=", "2024-12"),
            ]
        )

        self.assertEqual(len(cached_values), 3)

    def test_precompute_variable_none_strategy_fails(self):
        """Test pre-computation fails for cache_strategy='none' variables."""
        # Create a non-cached variable
        var = self.Variable.create(
            {
                "name": f"inline_var_{self._test_id}",
                "cel_accessor": f"inline_var_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "25",
                "cache_strategy": "none",
            }
        )

        # Attempt to pre-compute
        result = self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
        )

        # Assert failure with appropriate error message
        self.assertFalse(result["success"])
        self.assertIn("does not use persistent caching", result["error_message"])

    def test_precompute_variable_empty_subject_ids(self):
        """Test pre-computation with empty subject list."""
        var = self.Variable.create(
            {
                "name": f"var_{self._test_id}",
                "cel_accessor": f"var_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "10",
                "cache_strategy": "ttl",
            }
        )

        # Pre-compute with empty list
        result = self.cache_mgr.precompute_variable(
            var.name,
            [],
            period_key="current",
        )

        # Should succeed with no values computed
        self.assertTrue(result["success"])
        self.assertEqual(result["computed"], 0)
        self.assertEqual(result["cached"], 0)

    def test_precompute_variable_nonexistent(self):
        """Test pre-computation fails for nonexistent variable."""
        result = self.cache_mgr.precompute_variable(
            "nonexistent_variable_xyz",
            self.test_partners.ids,
        )

        self.assertFalse(result["success"])
        self.assertIn("not found or inactive", result["error_message"])

    # ═══════════════════════════════════════════════════════════════════════
    # BATCH PRE-COMPUTATION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_precompute_cached_variables_all(self):
        """Test batch pre-computation for all cached variables."""
        # Create multiple cached variables
        var1 = self.Variable.create(
            {
                "name": f"cached_var1_{self._test_id}",
                "cel_accessor": f"cached_var1_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "100",
                "cache_strategy": "ttl",
            }
        )
        var2 = self.Variable.create(
            {
                "name": f"cached_var2_{self._test_id}",
                "cel_accessor": f"cached_var2_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "200",
                "cache_strategy": "manual",
            }
        )
        # Non-cached variable (should be skipped)
        _var3 = self.Variable.create(
            {
                "name": f"inline_var_{self._test_id}",
                "cel_accessor": f"inline_var_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "50",
                "cache_strategy": "none",
            }
        )

        # Pre-compute all cached variables
        result = self.cache_mgr.precompute_cached_variables(
            self.test_partners.ids,
            period_key="current",
        )

        # Assert overall success
        self.assertTrue(result["success"])
        # Should process 2 cached variables (var1 and var2)
        # Note: there might be other cached variables in the system
        self.assertGreaterEqual(result["variables_processed"], 2)
        self.assertGreaterEqual(result["total_computed"], 6)  # 2 vars * 3 partners

        # Verify both variables were computed
        self.assertIn(var1.name, result["results"])
        self.assertIn(var2.name, result["results"])

        # Verify values exist in cache
        cached_var1 = self.DataValue.search(
            [
                ("variable_name", "=", var1.name),
            ]
        )
        cached_var2 = self.DataValue.search(
            [
                ("variable_name", "=", var2.name),
            ]
        )

        self.assertEqual(len(cached_var1), 3)
        self.assertEqual(len(cached_var2), 3)

    def test_precompute_cached_variables_specific_names(self):
        """Test batch pre-computation for specific variable names."""
        # Create multiple cached variables
        var1 = self.Variable.create(
            {
                "name": f"specific_var1_{self._test_id}",
                "cel_accessor": f"specific_var1_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "111",
                "cache_strategy": "ttl",
            }
        )
        var2 = self.Variable.create(
            {
                "name": f"specific_var2_{self._test_id}",
                "cel_accessor": f"specific_var2_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "222",
                "cache_strategy": "ttl",
            }
        )

        # Pre-compute only var1
        result = self.cache_mgr.precompute_cached_variables(
            self.test_partners.ids,
            period_key="current",
            variable_names=[var1.name],
        )

        # Assert success
        self.assertTrue(result["success"])
        self.assertEqual(result["variables_processed"], 1)

        # Verify only var1 was computed
        self.assertIn(var1.name, result["results"])
        self.assertNotIn(var2.name, result["results"])

        cached_var1 = self.DataValue.search(
            [
                ("variable_name", "=", var1.name),
            ]
        )
        cached_var2 = self.DataValue.search(
            [
                ("variable_name", "=", var2.name),
            ]
        )

        self.assertEqual(len(cached_var1), 3)
        self.assertEqual(len(cached_var2), 0)

    def test_precompute_cached_variables_empty_subjects(self):
        """Test batch pre-computation with empty subject list."""
        result = self.cache_mgr.precompute_cached_variables(
            [],
            period_key="current",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["variables_processed"], 0)
        self.assertEqual(result["total_computed"], 0)

    def test_precompute_cached_variables_no_cached_vars(self):
        """Test batch pre-computation when no cached variables exist."""
        # Pre-compute with specific names that don't exist
        result = self.cache_mgr.precompute_cached_variables(
            self.test_partners.ids,
            period_key="current",
            variable_names=["nonexistent_xyz"],
        )

        # Should succeed with warning
        self.assertTrue(result["success"])
        self.assertEqual(result["variables_processed"], 0)
        self.assertIn("No cached variables found", result["error_message"])

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE INVALIDATION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_invalidate_variable_specific_subjects(self):
        """Test cache invalidation for specific subjects."""
        # Create and pre-compute a variable
        var = self.Variable.create(
            {
                "name": f"invalidate_test_{self._test_id}",
                "cel_accessor": f"invalidate_test_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "99",
                "cache_strategy": "ttl",
            }
        )

        self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
        )

        # Verify values exist
        cached_before = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_before), 3)

        # Invalidate cache for 2 specific subjects
        count = self.cache_mgr.invalidate_variable(
            var.name,
            subject_ids=[self.partner_1.id, self.partner_2.id],
        )

        self.assertEqual(count, 2)

        # Verify only 1 value remains (partner_3)
        cached_after = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_after), 1)
        self.assertEqual(cached_after[0].subject_id, self.partner_3.id)

    def test_invalidate_variable_all_subjects(self):
        """Test cache invalidation for all subjects."""
        # Create and pre-compute a variable
        var = self.Variable.create(
            {
                "name": f"invalidate_all_{self._test_id}",
                "cel_accessor": f"invalidate_all_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "88",
                "cache_strategy": "ttl",
            }
        )

        self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
        )

        # Verify values exist
        cached_before = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_before), 3)

        # Invalidate all entries (no subject_ids parameter)
        count = self.cache_mgr.invalidate_variable(var.name)

        self.assertEqual(count, 3)

        # Verify no values remain
        cached_after = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_after), 0)

    def test_invalidate_variable_specific_period(self):
        """Test cache invalidation for specific period."""
        # Create and pre-compute a variable for multiple periods
        var = self.Variable.create(
            {
                "name": f"period_invalidate_{self._test_id}",
                "cel_accessor": f"period_invalidate_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "77",
                "cache_strategy": "ttl",
                "period_granularity": "monthly",  # Required for period_key to work
            }
        )

        # Pre-compute for different periods
        self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
            period_key="2024-11",
        )
        self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
            period_key="2024-12",
        )

        # Verify 6 values exist (3 per period)
        cached_before = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_before), 6)

        # Invalidate only 2024-11 period
        count = self.cache_mgr.invalidate_variable(
            var.name,
            period_key="2024-11",
        )

        self.assertEqual(count, 3)

        # Verify only 2024-12 values remain
        cached_after = self.DataValue.search(
            [
                ("variable_name", "=", var.name),
            ]
        )
        self.assertEqual(len(cached_after), 3)
        self.assertTrue(all(cv.period_key == "2024-12" for cv in cached_after))

    def test_invalidate_nonexistent_variable(self):
        """Test invalidation of nonexistent variable."""
        count = self.cache_mgr.invalidate_variable(
            "nonexistent_xyz_123",
        )
        self.assertEqual(count, 0)

    # ═══════════════════════════════════════════════════════════════════════
    # REFRESH OPERATIONS TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_refresh_variable(self):
        """Test refreshing a variable's cached values."""
        # Create a variable
        var = self.Variable.create(
            {
                "name": f"refresh_test_{self._test_id}",
                "cel_accessor": f"refresh_test_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "100",
                "cache_strategy": "ttl",
            }
        )

        # Initial pre-compute
        self.cache_mgr.precompute_variable(
            var.name,
            self.test_partners.ids,
        )

        # Modify the variable
        var.write({"default_value": "200"})

        # Refresh the cache
        refreshed = self.cache_mgr.refresh_variable(
            var.name,
            self.test_partners.ids,
        )

        # Verify refreshed values
        self.assertEqual(len(refreshed), 3)
        for _subject_id, value in refreshed.items():
            self.assertEqual(value, 200)

    def test_refresh_variables_for_subject(self):
        """Test refreshing all variables for a specific subject."""
        # Create multiple cached variables
        var1 = self.Variable.create(
            {
                "name": f"subject_refresh1_{self._test_id}",
                "cel_accessor": f"subject_refresh1_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "11",
                "cache_strategy": "ttl",
            }
        )
        var2 = self.Variable.create(
            {
                "name": f"subject_refresh2_{self._test_id}",
                "cel_accessor": f"subject_refresh2_{self._test_id}",
                "source_type": "constant",
                "value_type": "number",
                "default_value": "22",
                "cache_strategy": "manual",
            }
        )

        # Refresh all cached variables for partner_1
        result = self.cache_mgr.refresh_variables_for_subject(
            self.partner_1.id,
            variable_names=[var1.name, var2.name],
        )

        # Verify both variables were refreshed
        self.assertIn(var1.name, result)
        self.assertIn(var2.name, result)
        self.assertEqual(result[var1.name], 11)
        self.assertEqual(result[var2.name], 22)

    # ═══════════════════════════════════════════════════════════════════════
    # SESSION CACHE TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_session_cache_cleared(self):
        """Test session cache can be cleared."""
        # Directly populate session cache (session cache is in-memory, not via precompute)
        company_id = self.env.company.id
        var_name = f"session_var_{self._test_id}"

        # Manually add entries to session cache (thread-local)
        thread_local = self.cache_mgr.__class__._session_cache
        thread_local.cache = {
            (company_id, var_name, self.partner_1.id, "current"): 33,
            (company_id, var_name, self.partner_2.id, "current"): 33,
        }

        # Get stats before clear
        stats_before = self.cache_mgr.get_session_cache_stats()
        self.assertGreater(stats_before["size"], 0)

        # Clear session cache
        self.cache_mgr.clear_session_cache()

        # Verify cache is empty
        stats_after = self.cache_mgr.get_session_cache_stats()
        self.assertEqual(stats_after["size"], 0)

    def test_session_cache_stats(self):
        """Test session cache statistics."""
        # Directly populate session cache (session cache is in-memory)
        company_id = self.env.company.id
        var1_name = f"session_stat1_{self._test_id}"
        var2_name = f"session_stat2_{self._test_id}"

        # Manually add entries to session cache (thread-local)
        thread_local = self.cache_mgr.__class__._session_cache
        thread_local.cache = {
            (company_id, var1_name, self.partner_1.id, "current"): 44,
            (company_id, var2_name, self.partner_1.id, "current"): 55,
        }

        # Get stats
        stats = self.cache_mgr.get_session_cache_stats()

        # Should have entries for both variables
        self.assertEqual(stats["size"], 2)
        self.assertIn(var1_name, stats["variables"])
        self.assertIn(var2_name, stats["variables"])


@tagged("post_install", "-at_install")
class TestExternalProviderDispatch(TransactionCase, CELTestDataMixin):
    """Test that `_compute_variable_values` dispatches to the provider hook.

    The base provider's `_compute_external_values` is a no-op that returns {}
    and warns. Downstream modules override it; here we patch the method to
    verify the cache manager actually routes through the provider record.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.cache_mgr = cls.env["spp.data.cache.manager"]
        cls.Provider = cls.env["spp.data.provider"]
        cls.partner_a = cls._create_test_partner(name=f"Subject A {cls._test_id}")
        cls.partner_b = cls._create_test_partner(name=f"Subject B {cls._test_id}")
        cls.category = cls._create_test_category()
        cls.provider = cls.Provider.create(
            {
                "name": "Test External Provider",
                "code": f"test_ext_{cls._test_id}",
            }
        )
        cls.variable = cls._create_test_variable(
            name=f"ext_var_{cls._test_id}",
            source_type="external",
            value_type="number",
            cache_strategy="ttl",
            category=cls.category,
            external_provider_id=cls.provider.id,
        )

    def test_compute_dispatches_to_provider_hook(self):
        """`_compute_variable_values` calls `provider._compute_external_values`."""
        subject_ids = [self.partner_a.id, self.partner_b.id]
        expected = {self.partner_a.id: 11, self.partner_b.id: 22}

        with patch.object(
            type(self.provider),
            "_compute_external_values",
            return_value=expected,
        ) as mocked:
            result = self.cache_mgr._compute_variable_values(
                self.variable, subject_ids, period_key="current", program_id=None
            )

        self.assertEqual(result, expected)
        mocked.assert_called_once()
        # Verify the variable and subject list were forwarded.
        args, _kwargs = mocked.call_args
        self.assertEqual(args[0].id, self.variable.id)
        self.assertEqual(list(args[1]), subject_ids)
        self.assertEqual(args[2], "current")

    @mute_logger("odoo.addons.spp_cel_domain.models.data_provider")
    def test_compute_base_provider_no_op_returns_empty(self):
        """Base provider's hook returns {} and warns (no override installed)."""
        result = self.provider._compute_external_values(self.variable, [self.partner_a.id], "current")
        self.assertEqual(result, {})

    def test_precompute_external_variable_stores_provider_code(self):
        """Precomputed external cache rows are scoped to the provider code."""
        expected = {self.partner_a.id: 11}

        with patch.object(
            type(self.provider),
            "_compute_external_values",
            return_value=expected,
        ):
            result = self.cache_mgr.precompute_variable(
                self.variable.name,
                [self.partner_a.id],
                period_key="current",
            )

        self.assertTrue(result["success"])
        cached = self.env["spp.data.value"].search(
            [
                ("variable_name", "=", self.variable.name),
                ("subject_id", "=", self.partner_a.id),
                ("period_key", "=", "current"),
            ],
            limit=1,
        )
        self.assertTrue(cached)
        self.assertEqual(cached.provider, self.provider.code)

    @mute_logger("odoo.addons.spp_cel_domain.models.data_evaluator")
    def test_compute_external_without_provider_returns_empty(self):
        """An external variable with no provider returns {} (and warns)."""
        orphan_var = self._create_test_variable(
            name=f"orphan_ext_{self._test_id}",
            source_type="external",
            value_type="number",
            category=self.category,
            external_provider_id=False,
        )
        # The constraint normally prevents this, so bypass with a write that
        # the runtime ACL allows (constraint check happens at create/write of
        # `external_provider_id` itself; a False here means the variable is
        # mid-config). Using sudo to bypass the constraint is OK in tests
        # because we only want to verify the dispatch path.
        self.env.cr.execute(
            "UPDATE spp_cel_variable SET external_provider_id = NULL WHERE id = %s",
            (orphan_var.id,),
        )
        orphan_var.invalidate_recordset()
        result = self.cache_mgr._compute_variable_values(
            orphan_var, [self.partner_a.id], period_key="current", program_id=None
        )
        self.assertEqual(result, {})


@tagged("post_install", "-at_install")
class TestExternalMetricExecution(TransactionCase, CELTestDataMixin):
    """Tests for lazy metric execution of external variables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Provider = cls.env["spp.data.provider"]
        cls.DataValue = cls.env["spp.data.value"]
        cls.executor = cls.env["spp.cel.executor"]
        cls.service = cls.env["spp.cel.service"]
        cls.partner_a = cls._create_test_partner(name=f"Metric Subject A {cls._test_id}")
        cls.partner_b = cls._create_test_partner(name=f"Metric Subject B {cls._test_id}")
        cls.category = cls._create_test_category()
        cls.provider_a = cls.Provider.create(
            {
                "name": "Metric Provider A",
                "code": f"metric_provider_a_{cls._test_id}",
            }
        )
        cls.provider_b = cls.Provider.create(
            {
                "name": "Metric Provider B",
                "code": f"metric_provider_b_{cls._test_id}",
            }
        )

    def test_external_metric_uses_variable_name_when_metric_is_accessor(self):
        """A CEL accessor resolves to the external variable's cache variable_name."""
        variable = self._create_test_variable(
            name=f"notary_claim_name_{self._test_id}",
            cel_accessor=f"notary_claim_accessor_{self._test_id}",
            source_type="external",
            value_type="number",
            cache_strategy="ttl",
            category=self.category,
            external_provider_id=self.provider_a.id,
        )
        self.DataValue.upsert_values(
            [
                {
                    "variable_name": variable.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": self.provider_a.code,
                    "value_json": {"value": 42},
                    "value_type": "number",
                    "source_type": "external",
                    "ttl_seconds": 3600,
                },
                {
                    "variable_name": variable.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": "",
                    "value_json": {"value": 100},
                    "value_type": "number",
                    "source_type": "external",
                    "ttl_seconds": 3600,
                },
            ]
        )

        result = self.service.compile_expression(
            f"{variable.cel_accessor} >= 40",
            "registry_individuals",
            base_domain=[("id", "=", self.partner_a.id)],
        )

        self.assertTrue(result["valid"], result.get("error"))
        self.assertIn(self.partner_a.id, result["ids"])

    def test_external_metric_does_not_fall_back_to_other_provider(self):
        """External metric lookup must not use a row from another provider."""
        variable = self._create_test_variable(
            name=f"provider_scoped_metric_{self._test_id}",
            source_type="external",
            value_type="number",
            cache_strategy="ttl",
            category=self.category,
            external_provider_id=self.provider_a.id,
        )
        self.DataValue.upsert_values(
            [
                {
                    "variable_name": variable.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": self.provider_b.code,
                    "value_json": {"value": 99},
                    "value_type": "number",
                    "source_type": "external",
                    "ttl_seconds": 3600,
                },
                {
                    "variable_name": variable.name,
                    "subject_id": self.partner_a.id,
                    "period_key": "current",
                    "provider": "",
                    "value_json": {"value": 100},
                    "value_type": "number",
                    "source_type": "external",
                    "ttl_seconds": 3600,
                },
            ]
        )
        plan = MetricCompare(
            metric=variable.name,
            subject_var="me",
            period_key="current",
            params=None,
            op=">=",
            rhs=90,
        )
        executor = self.executor.with_context(
            cel_cfg={"base_domain": [("id", "=", self.partner_a.id)], "root_model": "res.partner"}
        )

        with patch.object(
            type(self.provider_a),
            "_compute_external_values",
            return_value={},
        ) as mocked_compute:
            result = executor._exec_metric("res.partner", plan)

        self.assertEqual(result, [])
        mocked_compute.assert_called_once()
