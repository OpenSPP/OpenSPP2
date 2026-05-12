# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests to close remaining coverage gaps in spp_analytics.

Targets untested branches and error-handling paths across all source files.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AnalyticsTestCase


@tagged("post_install", "-at_install")
class TestScopeRegistrantCountErrorHandling(AnalyticsTestCase):
    """Tests for _compute_registrant_count error paths in analytics_scope.py."""

    def test_registrant_count_returns_zero_on_validation_error(self):
        """_compute_registrant_count catches ValidationError and sets count to 0."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )
        with patch.object(
            type(self.env["spp.analytics.scope.resolver"]),
            "resolve",
            side_effect=ValidationError("test error"),
        ):
            scope._compute_registrant_count()
            self.assertEqual(scope.registrant_count, 0)

    def test_registrant_count_returns_zero_on_user_error(self):
        """_compute_registrant_count catches UserError and sets count to 0."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )
        with patch.object(
            type(self.env["spp.analytics.scope.resolver"]),
            "resolve",
            side_effect=UserError("test error"),
        ):
            scope._compute_registrant_count()
            self.assertEqual(scope.registrant_count, 0)

    def test_registrant_count_for_area_scope_resolves(self):
        """_compute_registrant_count resolves non-explicit scopes via resolver."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )
        # Area scope should resolve to registrants in that area
        self.assertGreater(scope.registrant_count, 0)


@tagged("post_install", "-at_install")
class TestActionRefreshCacheWithEntries(AnalyticsTestCase):
    """Tests for action_refresh_cache when cache entries exist."""

    def test_action_refresh_cache_invalidates_existing_entries(self):
        """action_refresh_cache invalidates cache entries for the scope's type."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )
        # Store a cache entry for this scope type
        cache_service = self.env["spp.analytics.cache"]
        cache_service.store_result(scope, ["count"], [], {"total_count": 10})

        # Verify entry exists
        entries_before = self.env["spp.analytics.cache.entry"].sudo().search([("scope_type", "=", "area")])
        self.assertTrue(entries_before)

        # Refresh cache
        scope.action_refresh_cache()

        # Entries should be invalidated
        entries_after = self.env["spp.analytics.cache.entry"].sudo().search([("scope_type", "=", "area")])
        self.assertFalse(entries_after)


@tagged("post_install", "-at_install")
class TestComputeStatisticsErrorHandling(AnalyticsTestCase):
    """Tests for _compute_statistics exception handling in service_aggregation.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]

    def test_compute_statistics_catches_value_error(self):
        """_compute_statistics catches ValueError and returns error dict."""
        with patch.object(
            type(self.env["spp.analytics.indicator.registry"]),
            "compute",
            side_effect=ValueError("bad value"),
        ):
            result = self.service._compute_statistics(self.registrants[:5].ids, ["count"], k_threshold=5)
            self.assertIn("count", result)
            self.assertIsNone(result["count"]["value"])
            self.assertIn("error", result["count"])
            self.assertFalse(result["count"]["suppressed"])

    def test_compute_statistics_catches_attribute_error(self):
        """_compute_statistics catches AttributeError and returns error dict."""
        with patch.object(
            type(self.env["spp.analytics.indicator.registry"]),
            "compute",
            side_effect=AttributeError("no such attr"),
        ):
            result = self.service._compute_statistics(self.registrants[:5].ids, ["some_stat"], k_threshold=5)
            self.assertIn("some_stat", result)
            self.assertIsNone(result["some_stat"]["value"])
            self.assertIn("error", result["some_stat"])

    def test_compute_statistics_catches_type_error(self):
        """_compute_statistics catches TypeError and returns error dict."""
        with patch.object(
            type(self.env["spp.analytics.indicator.registry"]),
            "compute",
            side_effect=TypeError("wrong type"),
        ):
            result = self.service._compute_statistics(self.registrants[:3].ids, ["count"], k_threshold=5)
            self.assertIn("count", result)
            self.assertIsNone(result["count"]["value"])

    def test_compute_statistics_catches_key_error(self):
        """_compute_statistics catches KeyError and returns error dict."""
        with patch.object(
            type(self.env["spp.analytics.indicator.registry"]),
            "compute",
            side_effect=KeyError("missing key"),
        ):
            result = self.service._compute_statistics(self.registrants[:3].ids, ["count"], k_threshold=5)
            self.assertIn("count", result)
            self.assertIsNone(result["count"]["value"])


@tagged("post_install", "-at_install")
class TestCacheServiceEdgeCases(AnalyticsTestCase):
    """Tests for cache service error handling and edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.analytics.cache"]

    def test_get_cached_result_handles_invalid_json(self):
        """get_cached_result returns None and cleans up entry with invalid JSON."""
        scope = self.create_scope("area", area_id=self.area_district.id)
        # Store valid entry first
        self.cache_service.store_result(scope, ["count"], [], {"total": 5})

        # Corrupt the JSON in the entry
        entry = self.env["spp.analytics.cache.entry"].sudo().search([], limit=1)
        entry.write({"result_json": "not valid json {"})

        # Should return None and clean up the bad entry
        result = self.cache_service.get_cached_result(scope, ["count"], [])
        self.assertIsNone(result)

        # Entry should be deleted
        remaining = self.env["spp.analytics.cache.entry"].sudo().search([("id", "=", entry.id)])
        self.assertFalse(remaining)

    def test_get_cached_result_removes_expired_entry(self):
        """get_cached_result removes expired entries and returns None."""
        scope = self.create_scope("area", area_id=self.area_district.id)
        self.cache_service.store_result(scope, ["count"], [], {"total": 5})

        # Backdate the entry to make it expired
        entry = self.env["spp.analytics.cache.entry"].sudo().search([], limit=1)
        expired_time = fields.Datetime.now() - timedelta(seconds=7200)
        entry.write({"computed_at": expired_time})

        # Should return None
        result = self.cache_service.get_cached_result(scope, ["count"], [])
        self.assertIsNone(result)

        # Expired entry should be removed
        remaining = self.env["spp.analytics.cache.entry"].sudo().search([("id", "=", entry.id)])
        self.assertFalse(remaining)

    def test_store_result_updates_existing_entry(self):
        """store_result updates existing entry when cache key matches."""
        scope = self.create_scope("area", area_id=self.area_district.id)

        # Store initial result
        self.cache_service.store_result(scope, ["count"], [], {"total": 5})
        entry = self.env["spp.analytics.cache.entry"].sudo().search([], limit=1)
        original_json = entry.result_json

        # Store updated result with same key
        self.cache_service.store_result(scope, ["count"], [], {"total": 10})

        # Should still be one entry, but with updated content
        entries = self.env["spp.analytics.cache.entry"].sudo().search([])
        area_entries = entries.filtered(lambda e: e.scope_type == "area")
        self.assertEqual(len(area_entries), 1)
        self.assertNotEqual(area_entries.result_json, original_json)
        self.assertIn("10", area_entries.result_json)

    def test_cache_resolve_scope_with_int(self):
        """Cache _resolve_scope handles integer scope ID."""
        scope = self.create_scope("area", area_id=self.area_district.id)
        resolved = self.cache_service._resolve_scope(scope.id)
        self.assertEqual(resolved.id, scope.id)


@tagged("post_install", "-at_install")
class TestScopeResolverErrorPaths(AnalyticsTestCase):
    """Tests for scope resolver error handling paths."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.analytics.scope.resolver"]

    def test_resolve_record_catches_exception_in_resolver_method(self):
        """resolve() catches exceptions from resolver methods and returns empty."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        with patch.object(
            type(self.resolver),
            "_resolve_explicit",
            side_effect=RuntimeError("resolver failed"),
        ):
            result = self.resolver.resolve(scope)
            self.assertEqual(result, [])

    def test_resolve_inline_catches_exception_in_resolver(self):
        """_resolve_inline catches exceptions from inline resolver methods."""
        scope_dict = {
            "scope_type": "explicit",
            "explicit_partner_ids": [1, 2, 3],
        }
        with patch.object(
            type(self.resolver),
            "_resolve_explicit_inline",
            side_effect=RuntimeError("inline resolver failed"),
        ):
            result = self.resolver.resolve(scope_dict)
            self.assertEqual(result, [])

    def test_resolve_explicit_inline_filters_non_registrants(self):
        """_resolve_explicit_inline filters out non-registrant partner IDs."""
        # Create a non-registrant partner
        non_registrant = self.env["res.partner"].create(
            {
                "name": "Not A Registrant",
                "is_registrant": False,
            }
        )
        # Mix registrant and non-registrant IDs
        mixed_ids = self.registrants[:3].ids + [non_registrant.id]
        scope_dict = {
            "scope_type": "explicit",
            "explicit_partner_ids": mixed_ids,
        }
        result = self.resolver._resolve_explicit_inline(scope_dict)
        # Non-registrant should be filtered out
        self.assertNotIn(non_registrant.id, result)
        self.assertEqual(len(result), 3)

    def test_resolve_explicit_inline_empty_list(self):
        """_resolve_explicit_inline with empty list returns empty."""
        result = self.resolver._resolve_explicit_inline({"scope_type": "explicit", "explicit_partner_ids": []})
        self.assertEqual(result, [])

    def test_resolve_area_with_membership_indirect_resolution(self):
        """_resolve_area_ids finds individuals via group membership."""
        # Create a group in the district
        group = self.env["res.partner"].create(
            {
                "name": "Test Group for Membership",
                "is_registrant": True,
                "is_group": True,
                "area_id": self.area_district.id,
            }
        )
        # Create an individual WITHOUT area_id
        individual = self.env["res.partner"].create(
            {
                "name": "Individual No Area",
                "is_registrant": True,
                "is_group": False,
                "area_id": False,
            }
        )
        # Create membership linking individual to group
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": individual.id,
            }
        )

        # Resolve area should find both the group and the individual
        result = self.resolver._resolve_area_ids([self.area_district.id], include_children=False)
        self.assertIn(group.id, result)
        self.assertIn(individual.id, result)

    def test_resolve_area_no_area_ids_returns_empty(self):
        """_resolve_area_ids with empty list returns empty."""
        result = self.resolver._resolve_area_ids([], include_children=True)
        self.assertEqual(result, [])

    def test_resolve_area_inline_missing_area_id_returns_empty(self):
        """_resolve_area_inline with no area_id returns empty."""
        result = self.resolver._resolve_area_inline({"scope_type": "area"})
        self.assertEqual(result, [])

    def test_resolve_area_record_missing_area_returns_empty(self):
        """_resolve_area with scope record where area_id is unset returns empty."""
        scope = self.create_scope("area", area_id=self.area_district.id)
        # Directly call _resolve_area with a scope that has no area
        with patch.object(type(scope), "area_id", new_callable=lambda: property(lambda s: self.env["spp.area"])):
            result = self.resolver._resolve_area(scope)
            self.assertEqual(result, [])

    def test_resolve_area_tag_inline_empty_tags_returns_empty(self):
        """_resolve_area_tag_inline with no tag_ids returns empty."""
        result = self.resolver._resolve_area_tag_inline({"scope_type": "area_tag"})
        self.assertEqual(result, [])

    def test_resolve_area_tag_record_empty_tags_returns_empty(self):
        """_resolve_area_tag with scope that has no tags returns empty."""
        scope = self.create_scope(
            "area_tag",
            area_tag_ids=[(6, 0, [self.tag_urban.id])],
        )
        # Patch tag_ids to empty
        with patch.object(
            type(scope),
            "area_tag_ids",
            new_callable=lambda: property(lambda s: self.env["spp.area.tag"]),
        ):
            result = self.resolver._resolve_area_tag(scope)
            self.assertEqual(result, [])

    def test_resolve_spatial_buffer_params_missing_returns_empty(self):
        """_resolve_spatial_buffer_params with incomplete params returns empty."""
        # Missing radius
        result = self.resolver._resolve_spatial_buffer_params(1.0, 2.0, None)
        self.assertEqual(result, [])

        # Missing latitude
        result = self.resolver._resolve_spatial_buffer_params(None, 2.0, 10.0)
        self.assertEqual(result, [])

        # All zero (falsy)
        result = self.resolver._resolve_spatial_buffer_params(0, 0, 0)
        self.assertEqual(result, [])

    def test_resolve_spatial_buffer_without_bridge(self):
        """_resolve_spatial_buffer_params without bridge module returns empty."""
        if self.env.get("spp.analytics.spatial.resolver"):
            self.skipTest("Spatial bridge module is installed")
        result = self.resolver._resolve_spatial_buffer_params(1.5, 2.5, 10.0)
        self.assertEqual(result, [])


@tagged("post_install", "-at_install")
class TestIndicatorRegistryEdgeCases(AnalyticsTestCase):
    """Tests for indicator registry edge cases in indicator_registry.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ind_registry = cls.env["spp.analytics.indicator.registry"]

    def test_compute_from_variable_empty_registrants(self):
        """_compute_from_variable returns 0 for empty registrant list."""
        if self.env.get("spp.cel.variable") is None:
            self.skipTest("spp_cel not installed")
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_empty_reg_var",
                "cel_accessor": "test_empty_reg_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        result = self.ind_registry._compute_from_variable(variable, [])
        self.assertEqual(result, 0)

    def test_compute_from_variable_no_cel_service(self):
        """_compute_from_variable returns None when cel service unavailable."""
        if self.env.get("spp.cel.variable") is None:
            self.skipTest("spp_cel not installed")
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_no_cel_svc_var",
                "cel_accessor": "test_no_cel_svc_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        with patch.object(type(self.env), "get", return_value=None):
            result = self.ind_registry._compute_from_variable(variable, self.registrants[:3].ids)
            self.assertIsNone(result)

    def test_compute_from_variable_no_expression_returns_none(self):
        """_compute_from_variable returns None when variable has no expression."""
        if self.env.get("spp.cel.variable") is None:
            self.skipTest("spp_cel not installed")
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_no_expr_var",
                "cel_accessor": "test_no_expr_var",
                "source_type": "computed",
                "cel_expression": "",
                "value_type": "number",
                "state": "active",
            }
        )
        result = self.ind_registry._compute_from_variable(variable, self.registrants[:3].ids)
        # Empty expression should return None or 0
        # (returns None because expression is falsy)
        self.assertIn(result, (None, 0))

    def test_compute_from_variable_catches_exception(self):
        """_compute_from_variable catches exceptions from CEL compilation."""
        if self.env.get("spp.cel.variable") is None:
            self.skipTest("spp_cel not installed")
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_exc_var",
                "cel_accessor": "test_exc_var",
                "source_type": "computed",
                "cel_expression": "r.invalid_field_xyz",
                "value_type": "number",
                "state": "active",
            }
        )
        # Mock compile_expression to raise, verifying exception is caught
        cel_service = self.env["spp.cel.service"].sudo()
        with patch.object(
            type(cel_service),
            "compile_expression",
            side_effect=RuntimeError("CEL compilation failed"),
        ):
            result = self.ind_registry._compute_from_variable(variable, self.registrants[:3].ids)
            self.assertIsNone(result)

    def test_is_member_aggregate_without_source_type_field(self):
        """_is_member_aggregate returns False when variable lacks source_type field."""
        mock_var = MagicMock()
        mock_var._fields = {}  # No source_type field
        result = self.ind_registry._is_member_aggregate(mock_var, "members.count(m, true)")
        self.assertFalse(result)

    def test_is_member_aggregate_non_aggregate_type(self):
        """_is_member_aggregate returns False for non-aggregate source_type."""
        mock_var = MagicMock()
        mock_var._fields = {"source_type": True}
        mock_var.source_type = "computed"
        result = self.ind_registry._is_member_aggregate(mock_var, "members.count(m, true)")
        self.assertFalse(result)

    def test_is_member_aggregate_non_member_expression(self):
        """_is_member_aggregate returns False for non-members expression."""
        mock_var = MagicMock()
        mock_var._fields = {"source_type": True}
        mock_var.source_type = "aggregate"
        result = self.ind_registry._is_member_aggregate(mock_var, "r.some_field > 5")
        self.assertFalse(result)

    def test_is_member_aggregate_true_case(self):
        """_is_member_aggregate returns True for aggregate members.* expression."""
        mock_var = MagicMock()
        mock_var._fields = {"source_type": True}
        mock_var.source_type = "aggregate"
        result = self.ind_registry._is_member_aggregate(mock_var, "members.count(m, true)")
        self.assertTrue(result)

    def test_compute_member_aggregate_sum_missing_method(self):
        """_compute_member_aggregate_sum returns None when method not available."""
        mock_cel_service = MagicMock(spec=[])  # No evaluate_member_aggregate
        result = self.ind_registry._compute_member_aggregate_sum(
            mock_cel_service, "members.count(m, true)", self.registrants[:5].ids
        )
        self.assertIsNone(result)

    def test_compute_member_aggregate_sum_skips_non_groups(self):
        """_compute_member_aggregate_sum skips non-group registrants."""
        mock_cel_service = MagicMock()
        mock_cel_service.evaluate_member_aggregate.return_value = 3

        # Use only individual registrants (is_group=False)
        individual_ids = self.registrants.filtered(lambda r: not r.is_group).ids[:5]
        result = self.ind_registry._compute_member_aggregate_sum(
            mock_cel_service, "members.count(m, true)", individual_ids
        )
        # All are non-groups, so total should be 0
        self.assertEqual(result, 0)
        mock_cel_service.evaluate_member_aggregate.assert_not_called()

    def test_compute_member_aggregate_sum_handles_bool_true(self):
        """_compute_member_aggregate_sum counts True booleans as 1."""
        mock_cel_service = MagicMock()
        mock_cel_service.evaluate_member_aggregate.return_value = True

        # Use group registrants
        group_ids = self.registrants.filtered(lambda r: r.is_group).ids
        if not group_ids:
            self.skipTest("No group registrants in test data")
        result = self.ind_registry._compute_member_aggregate_sum(mock_cel_service, "members.count(m, true)", group_ids)
        self.assertEqual(result, len(group_ids))

    def test_compute_member_aggregate_sum_handles_bool_false(self):
        """_compute_member_aggregate_sum counts False booleans as 0."""
        mock_cel_service = MagicMock()
        mock_cel_service.evaluate_member_aggregate.return_value = False

        group_ids = self.registrants.filtered(lambda r: r.is_group).ids
        if not group_ids:
            self.skipTest("No group registrants in test data")
        result = self.ind_registry._compute_member_aggregate_sum(mock_cel_service, "members.count(m, true)", group_ids)
        self.assertEqual(result, 0)

    def test_compute_member_aggregate_sum_catches_exception(self):
        """_compute_member_aggregate_sum catches exceptions and returns None."""
        mock_cel_service = MagicMock()
        mock_cel_service.evaluate_member_aggregate.side_effect = RuntimeError("fail")

        group_ids = self.registrants.filtered(lambda r: r.is_group).ids
        if not group_ids:
            self.skipTest("No group registrants in test data")
        result = self.ind_registry._compute_member_aggregate_sum(mock_cel_service, "members.count(m, true)", group_ids)
        self.assertIsNone(result)

    def test_list_available_deduplicates_variables(self):
        """list_available does not duplicate names already in the list."""
        available = self.ind_registry.list_available()
        names = [a["name"] for a in available]
        # Built-ins should not be duplicated
        self.assertEqual(names.count("count"), 1)

    def test_compute_unknown_returns_none(self):
        """compute() returns None for completely unknown statistic."""
        result = self.ind_registry.compute("totally_unknown_stat_xyz_123", self.registrants[:3].ids)
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestCacheCleanupMultipleTypes(AnalyticsTestCase):
    """Tests for cache cleanup across multiple scope types."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.analytics.cache"]

    def test_cleanup_expired_removes_only_expired(self):
        """cleanup_expired removes expired entries but keeps fresh ones."""
        # Create entries for different scope types
        area_scope = self.create_scope("area", area_id=self.area_district.id)
        explicit_scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:3].ids)],
        )

        self.cache_service.store_result(area_scope, ["count"], [], {"total": 10})
        self.cache_service.store_result(explicit_scope, ["count"], [], {"total": 3})

        # Backdate area entry to make it expired (area TTL = 3600)
        area_entry = self.env["spp.analytics.cache.entry"].sudo().search([("scope_type", "=", "area")], limit=1)
        expired_time = fields.Datetime.now() - timedelta(seconds=7200)
        area_entry.write({"computed_at": expired_time})

        # Run cleanup
        removed = self.cache_service.cleanup_expired()
        self.assertGreaterEqual(removed, 1)

        # Area entry should be gone, explicit should remain
        remaining_area = self.env["spp.analytics.cache.entry"].sudo().search([("scope_type", "=", "area")])
        remaining_explicit = self.env["spp.analytics.cache.entry"].sudo().search([("scope_type", "=", "explicit")])
        self.assertFalse(remaining_area)
        self.assertTrue(remaining_explicit)

    def test_cleanup_expired_skips_non_cached_types(self):
        """cleanup_expired skips scope types with TTL=0 (spatial)."""
        # spatial_polygon has TTL=0, should never have cache entries
        # This just verifies cleanup runs without error
        removed = self.cache_service.cleanup_expired()
        self.assertIsInstance(removed, int)


@tagged("post_install", "-at_install")
class TestCacheHitPath(AnalyticsTestCase):
    """Tests for the cache hit path in compute_aggregation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]

    def test_compute_aggregation_returns_cached_result(self):
        """compute_aggregation returns cached result on second call."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )

        # First call populates cache
        result1 = self.service.compute_aggregation(scope, use_cache=True)
        self.assertFalse(result1["from_cache"])

        # Second call should return cached result
        result2 = self.service.compute_aggregation(scope, use_cache=True)
        self.assertTrue(result2["from_cache"])
        self.assertEqual(result1["total_count"], result2["total_count"])

    def test_cached_result_includes_access_level(self):
        """Cached result includes access_level from current user's rule."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
        )

        # First call
        self.service.compute_aggregation(scope, use_cache=True)

        # Second call (from cache)
        result = self.service.compute_aggregation(scope, use_cache=True)
        self.assertIn("access_level", result)


@tagged("post_install", "-at_install")
class TestResolveAreaWithChildAreas(AnalyticsTestCase):
    """Tests for area resolution with child area expansion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.analytics.scope.resolver"]

    def test_resolve_area_with_children_includes_all_levels(self):
        """_resolve_area_ids with include_children finds registrants at all levels."""
        # Registrants are in district and region. Resolving country with
        # children should find them all.
        result = self.resolver._resolve_area_ids([self.area_country.id], include_children=True)
        # Should include registrants from region and district
        self.assertGreater(len(result), 0)

    def test_resolve_area_without_children_only_direct(self):
        """_resolve_area_ids without children only finds direct registrants."""
        result_with = self.resolver._resolve_area_ids([self.area_country.id], include_children=True)
        result_without = self.resolver._resolve_area_ids([self.area_country.id], include_children=False)
        # Country has no direct registrants, but children do
        self.assertGreaterEqual(len(result_with), len(result_without))
