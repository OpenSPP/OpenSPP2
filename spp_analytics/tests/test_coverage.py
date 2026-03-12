# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extended coverage tests for spp_analytics module.

Covers edge cases in access rules, cache key generation,
scope resolver, and aggregation service convenience methods.
"""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import AnalyticsTestCase


@tagged("post_install", "-at_install")
class TestAccessRuleValidation(AnalyticsTestCase):
    """Tests for spp.analytics.access.rule constraint and validation edge cases."""

    def test_constraint_both_user_and_group_raises(self):
        """Setting both user_id and group_id must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "Invalid Rule",
                    "access_level": "aggregate",
                    "user_id": self.env.user.id,
                    "group_id": self.env.ref("base.group_user").id,
                }
            )

    def test_constraint_neither_user_nor_group_raises(self):
        """Clearing both user_id and group_id must raise ValidationError."""
        rule = self.create_access_rule("aggregate", user_id=self.env.user.id, group_id=False)
        with self.assertRaises(ValidationError):
            rule.write({"user_id": False})

    def test_constraint_k_anonymity_below_1_raises(self):
        """minimum_k_anonymity < 1 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "K Too Low",
                    "access_level": "aggregate",
                    "user_id": self.env.user.id,
                    "minimum_k_anonymity": 0,
                }
            )

    def test_constraint_k_anonymity_above_100_raises(self):
        """minimum_k_anonymity > 100 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "K Too High",
                    "access_level": "aggregate",
                    "user_id": self.env.user.id,
                    "minimum_k_anonymity": 101,
                }
            )

    def test_constraint_max_dimensions_negative_raises(self):
        """max_group_by_dimensions < 0 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "Negative Dims",
                    "access_level": "aggregate",
                    "user_id": self.env.user.id,
                    "max_group_by_dimensions": -1,
                }
            )

    def test_constraint_max_dimensions_above_10_raises(self):
        """max_group_by_dimensions > 10 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "Too Many Dims",
                    "access_level": "aggregate",
                    "user_id": self.env.user.id,
                    "max_group_by_dimensions": 11,
                }
            )

    def test_check_scope_allowed_inline_not_allowed(self):
        """Inline scope dict must be rejected when allow_inline_scopes is False."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allow_inline_scopes=False,
        )
        inline_scope = {"scope_type": "area", "area_id": self.area_region.id}
        with self.assertRaises(ValidationError):
            rule.check_scope_allowed(inline_scope)

    def test_check_scope_allowed_predefined_only_rejects_inline(self):
        """allowed_scope_types='predefined' must reject inline dict scopes."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allowed_scope_types="predefined",
            allow_inline_scopes=True,
        )
        inline_scope = {"scope_type": "area", "area_id": self.area_region.id}
        with self.assertRaises(ValidationError):
            rule.check_scope_allowed(inline_scope)

    def test_check_scope_allowed_predefined_with_allowed_scope_ids(self):
        """predefined mode with allowed_scope_ids must reject unlisted scopes."""
        allowed_scope = self.create_scope(
            "area",
            area_id=self.area_region.id,
        )
        other_scope = self.create_scope(
            "area",
            name="Other Scope",
            area_id=self.area_district.id,
        )
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allowed_scope_types="predefined",
            allowed_scope_ids=[(6, 0, [allowed_scope.id])],
        )
        # Allowed scope should pass
        self.assertTrue(rule.check_scope_allowed(allowed_scope))
        # Other scope should fail
        with self.assertRaises(ValidationError):
            rule.check_scope_allowed(other_scope)

    def test_check_scope_allowed_area_only_rejects_explicit(self):
        """allowed_scope_types='area_only' must reject explicit scope type."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allowed_scope_types="area_only",
            allow_inline_scopes=True,
        )
        explicit_scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        with self.assertRaises(ValidationError):
            rule.check_scope_allowed(explicit_scope)

    def test_check_scope_allowed_area_only_allows_area(self):
        """allowed_scope_types='area_only' must allow area scope type."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allowed_scope_types="area_only",
            allow_inline_scopes=True,
        )
        area_scope = self.create_scope(
            "area",
            area_id=self.area_region.id,
        )
        self.assertTrue(rule.check_scope_allowed(area_scope))

    def test_check_dimensions_allowed_exceeds_max(self):
        """Requesting more dimensions than max_group_by_dimensions must raise."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            max_group_by_dimensions=1,
        )
        with self.assertRaises(ValidationError):
            rule.check_dimensions_allowed(["dim_a", "dim_b"])

    def test_check_dimensions_allowed_disallowed_names(self):
        """Requesting dimensions not in allowed_dimension_ids must raise."""
        # Create dimensions
        dim_allowed = self.env["spp.demographic.dimension"].create(
            {
                "name": "test_allowed_dim",
                "label": "Allowed Dim",
                "dimension_type": "field",
                "field_path": "is_group",
            }
        )
        self.env["spp.demographic.dimension"].create(
            {
                "name": "test_forbidden_dim",
                "label": "Forbidden Dim",
                "dimension_type": "field",
                "field_path": "is_registrant",
            }
        )
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            allowed_dimension_ids=[(6, 0, [dim_allowed.id])],
        )
        # Allowed dimension should pass
        self.assertTrue(rule.check_dimensions_allowed(["test_allowed_dim"]))
        # Forbidden dimension should fail
        with self.assertRaises(ValidationError):
            rule.check_dimensions_allowed(["test_forbidden_dim"])

    def test_get_effective_rule_user_over_group(self):
        """User-specific rule must take precedence over group-based rule."""
        test_user = self.env["res.users"].create(
            {
                "name": "Priority Test User",
                "login": "priority_test_user",
                "email": "priority@test.com",
                "group_ids": [(4, self.env.ref("base.group_user").id)],
            }
        )
        # Create group-based rule
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "Group Rule",
                "access_level": "aggregate",
                "group_id": self.env.ref("base.group_user").id,
                "minimum_k_anonymity": 10,
                "sequence": 1,
            }
        )
        # Create user-specific rule
        user_rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "User Rule",
                "access_level": "individual",
                "user_id": test_user.id,
                "minimum_k_anonymity": 3,
                "sequence": 5,
            }
        )
        # User-specific rule should win regardless of sequence
        AccessRule = self.env["spp.analytics.access.rule"]
        effective = AccessRule.get_effective_rule_for_user(test_user)
        self.assertEqual(effective.id, user_rule.id)
        self.assertEqual(effective.access_level, "individual")


@tagged("post_install", "-at_install")
class TestCacheServiceKeyGeneration(AnalyticsTestCase):
    """Tests for cache key generation across all scope types."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.analytics.cache"]

    def test_scope_key_parts_dict_area(self):
        """Cache key parts for dict area scope must include area_id and children flag."""
        scope = {"scope_type": "area", "area_id": 42, "include_child_areas": False}
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("area", parts)
        self.assertIn("area:42", parts)
        self.assertIn("children:False", parts)

    def test_scope_key_parts_dict_cel(self):
        """Cache key parts for dict CEL scope must include expression and profile."""
        scope = {
            "scope_type": "cel",
            "cel_expression": "r.age >= 18",
            "cel_profile": "registry_groups",
        }
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("cel", parts)
        self.assertIn("expr:r.age >= 18", parts)
        self.assertIn("profile:registry_groups", parts)

    def test_scope_key_parts_dict_spatial_polygon(self):
        """Cache key parts for dict spatial_polygon scope must include geojson."""
        geojson = '{"type":"Polygon"}'
        scope = {"scope_type": "spatial_polygon", "geometry_geojson": geojson}
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("spatial_polygon", parts)
        self.assertIn(f"geojson:{geojson}", parts)

    def test_scope_key_parts_dict_spatial_buffer(self):
        """Cache key parts for dict spatial_buffer scope must include lat, lon, radius."""
        scope = {
            "scope_type": "spatial_buffer",
            "buffer_center_latitude": 1.5,
            "buffer_center_longitude": 2.5,
            "buffer_radius_km": 10.0,
        }
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("spatial_buffer", parts)
        self.assertIn("lat:1.5", parts)
        self.assertIn("lon:2.5", parts)
        self.assertIn("radius:10.0", parts)

    def test_scope_key_parts_dict_area_tag(self):
        """Cache key parts for dict area_tag scope must include sorted tag IDs."""
        scope = {"scope_type": "area_tag", "area_tag_ids": [3, 1, 2]}
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("area_tag", parts)
        self.assertIn("tags:[1, 2, 3]", parts)

    def test_scope_key_parts_dict_explicit(self):
        """Cache key parts for dict explicit scope must include sorted partner IDs."""
        scope = {"scope_type": "explicit", "explicit_partner_ids": [10, 5, 8]}
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("explicit", parts)
        self.assertIn("partners:[5, 8, 10]", parts)

    def test_scope_key_parts_record(self):
        """Cache key parts for scope record must include scope_type and scope_id."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        parts = self.cache_service._get_scope_key_parts(scope)
        self.assertIn("area", parts)
        self.assertIn(f"scope_id:{scope.id}", parts)

    def test_get_scope_type_dict(self):
        """_get_scope_type with dict must return scope_type value or 'explicit' default."""
        self.assertEqual(self.cache_service._get_scope_type({"scope_type": "cel"}), "cel")
        self.assertEqual(self.cache_service._get_scope_type({}), "explicit")

    def test_get_scope_type_record(self):
        """_get_scope_type with record must return the record's scope_type."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        self.assertEqual(self.cache_service._get_scope_type(scope), "area")

    def test_get_ttl_for_scope_type(self):
        """TTL lookup must return correct values and 0 for unknown types."""
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("area"), 3600)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("cel"), 900)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("spatial_polygon"), 0)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("spatial_buffer"), 0)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("area_tag"), 3600)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("explicit"), 1800)
        self.assertEqual(self.cache_service._get_ttl_for_scope_type("unknown_type"), 0)

    def test_cron_cleanup_expired(self):
        """cron_cleanup_expired on cache.entry must delegate to cache service."""
        cache_entry_model = self.env["spp.analytics.cache.entry"]
        # Should run without error and return an integer
        result = cache_entry_model.cron_cleanup_expired()
        self.assertIsInstance(result, int)

    def test_store_result_serialization_error(self):
        """store_result must return False when result cannot be serialized."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        with patch("odoo.addons.spp_analytics.models.service_cache.json.dumps", side_effect=TypeError("bad")):
            stored = self.cache_service.store_result(scope, ["count"], [], {"total": 1})
            self.assertFalse(stored)


@tagged("post_install", "-at_install")
class TestScopeResolverEdgeCases(AnalyticsTestCase):
    """Tests for scope resolver edge cases and error handling."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.analytics.scope.resolver"]

    def test_resolve_inline_missing_scope_type(self):
        """Inline scope dict without scope_type must return empty list."""
        result = self.resolver.resolve({"area_id": 1})
        self.assertEqual(result, [])

    def test_resolve_inline_unknown_scope_type(self):
        """Inline scope dict with unknown scope_type must return empty list."""
        result = self.resolver.resolve({"scope_type": "nonexistent_type"})
        self.assertEqual(result, [])

    def test_resolve_spatial_buffer_inline_missing_params(self):
        """Spatial buffer inline with missing params must return empty list."""
        result = self.resolver.resolve(
            {
                "scope_type": "spatial_buffer",
                # Missing latitude, longitude, and radius
            }
        )
        self.assertEqual(result, [])

    def test_resolve_spatial_polygon_inline_no_geojson(self):
        """Spatial polygon inline without geojson must return empty list."""
        result = self.resolver.resolve(
            {
                "scope_type": "spatial_polygon",
                # Missing geometry_geojson
            }
        )
        self.assertEqual(result, [])

    def test_resolve_record_unknown_scope_type(self):
        """Scope record with a scope_type that has no resolver method returns empty."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        # Temporarily patch scope_type to something unmapped
        with patch.object(type(scope), "scope_type", new_callable=lambda: property(lambda s: "bogus_type")):
            result = self.resolver.resolve(scope)
            self.assertEqual(result, [])

    def test_resolve_intersect_empty_scopes(self):
        """resolve_intersect with empty scope list must return empty list."""
        result = self.resolver.resolve_intersect([])
        self.assertEqual(result, [])


@tagged("post_install", "-at_install")
class TestAggregationServiceExtended(AnalyticsTestCase):
    """Extended tests for spp.analytics.service convenience methods and scope resolution."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]

    def test_resolve_scope_dict(self):
        """_resolve_scope with dict must return the same dict."""
        scope_dict = {"scope_type": "area", "area_id": self.area_region.id}
        result = self.service._resolve_scope(scope_dict)
        self.assertIs(result, scope_dict)

    def test_resolve_scope_int(self):
        """_resolve_scope with int must return a browse record."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        result = self.service._resolve_scope(scope.id)
        self.assertEqual(result.id, scope.id)
        self.assertEqual(result._name, "spp.analytics.scope")

    def test_resolve_scope_record(self):
        """_resolve_scope with record must return the same record."""
        scope = self.create_scope("area", area_id=self.area_region.id)
        result = self.service._resolve_scope(scope)
        self.assertIs(result, scope)

    def test_compute_for_area_convenience(self):
        """compute_for_area must build inline area scope and compute."""
        result = self.service.compute_for_area(
            self.area_district.id,
            include_children=False,
        )
        self.assertIn("total_count", result)
        self.assertGreater(result["total_count"], 0)
        self.assertIn("access_level", result)

    def test_compute_for_expression_convenience(self):
        """compute_for_expression must build inline CEL scope and compute."""
        result = self.service.compute_for_expression(
            cel_expression="r.is_group == false",
            profile="registry_individuals",
        )
        self.assertIn("total_count", result)

    def test_compute_fairness_convenience(self):
        """compute_fairness must resolve scope and delegate to fairness service."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:10].ids)],
        )
        result = self.service.compute_fairness(scope)
        self.assertIn("equity_score", result)
        self.assertIn("has_disparity", result)

    def test_compute_distribution_convenience(self):
        """compute_distribution must delegate to distribution service."""
        result = self.service.compute_distribution([10, 20, 30, 40, 50])
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["total"], 150)
        self.assertIn("gini_coefficient", result)

    def test_compute_with_use_cache_false(self):
        """compute_aggregation with use_cache=False must skip cache."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        result = self.service.compute_aggregation(scope, use_cache=False)
        self.assertFalse(result["from_cache"])
        self.assertEqual(result["total_count"], 5)

    def test_check_scope_allowed_no_rule(self):
        """_check_scope_allowed with no matching rule must pass silently."""
        # Create a user with no access rules
        user_no_rule = self.env["res.users"].create(
            {
                "name": "No Rule User",
                "login": "no_rule_user",
                "email": "norule@test.com",
            }
        )
        service = self.service.with_user(user_no_rule)
        # Should not raise -- no rule means default allow
        scope_dict = {"scope_type": "explicit", "explicit_partner_ids": self.registrants[:3].ids}
        service._check_scope_allowed(scope_dict)


@tagged("post_install", "-at_install")
class TestAnalyticsScopeActions(AnalyticsTestCase):
    """Tests for action_preview_registrants, action_refresh_cache, and _check_area_tags."""

    def test_action_preview_registrants_returns_act_window(self):
        """action_preview_registrants must return an ir.actions.act_window dict."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        action = scope.action_preview_registrants()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertIn("list,form", action["view_mode"])

    def test_action_preview_registrants_domain_contains_ids(self):
        """action_preview_registrants domain must restrict to scope's registrant IDs."""
        partner_ids = self.registrants[:3].ids
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, partner_ids)],
        )
        action = scope.action_preview_registrants()
        domain = action["domain"]
        # The domain should contain an 'id in [...]' filter
        self.assertTrue(any(condition[0] == "id" for condition in domain))
        id_condition = next(c for c in domain if c[0] == "id")
        self.assertEqual(set(id_condition[2]), set(partner_ids))

    def test_action_preview_registrants_name_includes_scope_name(self):
        """action_preview_registrants name must mention the scope name."""
        scope = self.create_scope(
            "explicit",
            name="My Preview Scope",
            explicit_partner_ids=[(6, 0, self.registrants[:2].ids)],
        )
        action = scope.action_preview_registrants()
        self.assertIn("My Preview Scope", action["name"])

    def test_action_preview_registrants_context_disables_create_delete(self):
        """action_preview_registrants context must set create and delete to False."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:2].ids)],
        )
        action = scope.action_preview_registrants()
        self.assertFalse(action["context"].get("create"))
        self.assertFalse(action["context"].get("delete"))

    def test_action_refresh_cache_returns_true(self):
        """action_refresh_cache must return True."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        result = scope.action_refresh_cache()
        self.assertTrue(result)

    def test_action_refresh_cache_updates_last_cache_refresh(self):
        """action_refresh_cache must write last_cache_refresh timestamp."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        self.assertFalse(scope.last_cache_refresh)
        scope.action_refresh_cache()
        self.assertTrue(scope.last_cache_refresh)

    def test_check_area_tags_raises_when_no_tags(self):
        """_check_area_tags must raise ValidationError when area_tag scope has no tags."""
        with self.assertRaises(ValidationError):
            self.create_scope("area_tag")

    def test_check_area_tags_passes_with_tags(self):
        """_check_area_tags must not raise when area_tag scope has tags."""
        scope = self.create_scope(
            "area_tag",
            area_tag_ids=[(6, 0, [self.tag_urban.id])],
        )
        self.assertTrue(scope.id)

    def test_check_area_tags_raises_when_tags_cleared(self):
        """_check_area_tags must raise if area_tags are cleared after creation."""
        scope = self.create_scope(
            "area_tag",
            area_tag_ids=[(6, 0, [self.tag_urban.id])],
        )
        with self.assertRaises(ValidationError):
            scope.write({"area_tag_ids": [(5, 0, 0)]})


@tagged("post_install", "-at_install")
class TestAggregationServiceInternals(AnalyticsTestCase):
    """Tests for internal methods of spp.analytics.service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]

    def test_get_effective_rule_returns_none_when_no_rule(self):
        """_get_effective_rule must return None (falsy) when no rule matches."""
        user_no_rule = self.env["res.users"].create(
            {
                "name": "Effective Rule Test User",
                "login": "effective_rule_test_user",
                "email": "effectiverule@test.com",
            }
        )
        service = self.service.with_user(user_no_rule)
        rule = service._get_effective_rule()
        self.assertFalse(rule)

    def test_get_effective_rule_returns_user_rule(self):
        """_get_effective_rule must return the matching rule for the current user."""
        test_user = self.env["res.users"].create(
            {
                "name": "Rule Test User",
                "login": "rule_test_user2",
                "email": "ruletest2@test.com",
            }
        )
        created_rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "Effective Rule For User",
                "access_level": "individual",
                "user_id": test_user.id,
            }
        )
        service = self.service.with_user(test_user)
        rule = service._get_effective_rule()
        self.assertTrue(rule)
        self.assertEqual(rule.id, created_rule.id)

    def test_access_level_from_rule_returns_rule_level(self):
        """_access_level_from_rule must return the rule's access_level when rule present."""
        rule = self.create_access_rule("individual", user_id=self.env.user.id, group_id=False)
        level = self.service._access_level_from_rule(rule)
        self.assertEqual(level, "individual")

    def test_access_level_from_rule_defaults_to_aggregate_when_none(self):
        """_access_level_from_rule must return 'aggregate' when rule is None/falsy."""
        level = self.service._access_level_from_rule(None)
        self.assertEqual(level, "aggregate")

    def test_k_threshold_from_rule_returns_rule_threshold(self):
        """_k_threshold_from_rule must return minimum_k_anonymity from rule."""
        rule = self.create_access_rule(
            "aggregate",
            user_id=self.env.user.id,
            group_id=False,
            minimum_k_anonymity=7,
        )
        threshold = self.service._k_threshold_from_rule(rule)
        self.assertEqual(threshold, 7)

    def test_k_threshold_from_rule_uses_privacy_default_when_none(self):
        """_k_threshold_from_rule must fall back to privacy service default when no rule."""
        threshold = self.service._k_threshold_from_rule(None)
        privacy_default = self.env["spp.metric.privacy"].DEFAULT_K_THRESHOLD
        self.assertEqual(threshold, privacy_default)

    def test_compute_single_statistic_delegates_to_registry(self):
        """_compute_single_statistic must delegate to indicator registry."""
        ids = self.registrants[:5].ids
        result = self.service._compute_single_statistic("count", ids)
        self.assertEqual(result, 5)

    def test_compute_single_statistic_returns_none_for_unknown(self):
        """_compute_single_statistic must return None for an unknown statistic."""
        result = self.service._compute_single_statistic("unknown_stat_xyz", self.registrants[:3].ids)
        self.assertIsNone(result)

    def test_compute_breakdown_returns_dict(self):
        """_compute_breakdown must return a dict with breakdown cells."""
        ids = self.registrants.ids
        result = self.service._compute_breakdown(ids, ["registrant_type"], None, None)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_compute_breakdown_with_statistics(self):
        """_compute_breakdown with statistics must include stats per cell."""
        ids = self.registrants.ids
        result = self.service._compute_breakdown(ids, ["registrant_type"], ["count"], None)
        self.assertIsInstance(result, dict)
        # Each cell should have a count key
        for _cell_key, cell in result.items():
            self.assertIn("count", cell)


@tagged("post_install", "-at_install")
class TestScopeResolverCelMethods(AnalyticsTestCase):
    """Tests for CEL resolution methods in spp.analytics.scope.resolver."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.analytics.scope.resolver"]

    def test_resolve_cel_record_without_executor_returns_empty(self):
        """_resolve_cel with a CEL scope record returns empty when executor unavailable."""
        scope = self.create_scope(
            "cel",
            cel_expression="r.is_group == false",
            cel_profile="registry_individuals",
        )
        # When spp.cel.executor is not installed the resolver logs an error and returns []
        if self.env.get("spp.cel.executor") is None:
            result = self.resolver._resolve_cel(scope)
            self.assertEqual(result, [])
        else:
            # Module IS installed; just check it returns a list
            result = self.resolver._resolve_cel(scope)
            self.assertIsInstance(result, list)

    def test_resolve_cel_record_empty_expression_returns_empty(self):
        """_resolve_cel_expression with empty string must return empty list."""
        result = self.resolver._resolve_cel_expression("", "registry_individuals")
        self.assertEqual(result, [])

    def test_resolve_cel_inline_without_executor_returns_empty(self):
        """_resolve_cel_inline with an inline CEL scope returns empty when executor unavailable."""
        scope_dict = {
            "scope_type": "cel",
            "cel_expression": "r.is_group == false",
            "cel_profile": "registry_individuals",
        }
        if self.env.get("spp.cel.executor") is None:
            result = self.resolver._resolve_cel_inline(scope_dict)
            self.assertEqual(result, [])
        else:
            result = self.resolver._resolve_cel_inline(scope_dict)
            self.assertIsInstance(result, list)

    def test_resolve_cel_inline_missing_expression_returns_empty(self):
        """_resolve_cel_inline with missing cel_expression returns empty list."""
        scope_dict = {
            "scope_type": "cel",
            # No cel_expression key
        }
        result = self.resolver._resolve_cel_inline(scope_dict)
        self.assertEqual(result, [])

    def test_resolve_dispatches_to_resolve_cel(self):
        """resolve() on a CEL record scope must call the CEL resolver, not raise."""
        scope = self.create_scope(
            "cel",
            cel_expression="r.is_group == false",
        )
        # Should not raise; returns a list (possibly empty if executor missing)
        result = self.resolver.resolve(scope)
        self.assertIsInstance(result, list)


@tagged("post_install", "-at_install")
class TestIndicatorRegistryInternals(TransactionCase):
    """Tests for internal dispatch methods of spp.analytics.indicator.registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.indicator_registry = cls.env["spp.analytics.indicator.registry"]
        cls.registrants = cls.env["res.partner"]
        for i in range(10):
            cls.registrants |= cls.env["res.partner"].create(
                {
                    "name": f"Registry Internals Test {i}",
                    "is_registrant": True,
                }
            )

    def test_get_builtin_returns_method_for_count(self):
        """_get_builtin('count') must return a callable."""
        method = self.indicator_registry._get_builtin("count")
        self.assertIsNotNone(method)
        self.assertTrue(callable(method))

    def test_get_builtin_returns_method_for_gini(self):
        """_get_builtin('gini') must return a callable."""
        method = self.indicator_registry._get_builtin("gini")
        self.assertIsNotNone(method)
        self.assertTrue(callable(method))

    def test_get_builtin_returns_method_for_gini_coefficient_alias(self):
        """_get_builtin('gini_coefficient') must return a callable (alias)."""
        method = self.indicator_registry._get_builtin("gini_coefficient")
        self.assertIsNotNone(method)
        self.assertTrue(callable(method))

    def test_get_builtin_returns_none_for_unknown(self):
        """_get_builtin must return None for an unregistered statistic name."""
        method = self.indicator_registry._get_builtin("no_such_stat")
        self.assertIsNone(method)

    def test_get_builtin_count_callable_returns_correct_count(self):
        """The callable returned by _get_builtin('count') must compute correctly."""
        method = self.indicator_registry._get_builtin("count")
        result = method(self.registrants[:7].ids)
        self.assertEqual(result, 7)

    def test_try_statistic_model_returns_none_when_model_absent(self):
        """_try_statistic_model returns None when spp.indicator is not installed."""
        if self.env.get("spp.indicator") is not None:
            self.skipTest("spp_indicator is installed; testing absence is not possible")
        result = self.indicator_registry._try_statistic_model("some_stat", self.registrants.ids)
        self.assertIsNone(result)

    def test_try_statistic_model_returns_none_for_missing_stat(self):
        """_try_statistic_model returns None when named statistic record does not exist."""
        if self.env.get("spp.indicator") is None:
            self.skipTest("spp_indicator not installed")
        result = self.indicator_registry._try_statistic_model("nonexistent_stat_abc", self.registrants.ids)
        self.assertIsNone(result)

    def test_try_variable_model_returns_none_when_model_absent(self):
        """_try_variable_model returns None when spp.cel.variable is not installed."""
        if self.env.get("spp.cel.variable") is not None:
            self.skipTest("spp_cel is installed; testing absence is not possible")
        result = self.indicator_registry._try_variable_model("some_var", self.registrants.ids)
        self.assertIsNone(result)

    def test_try_variable_model_returns_none_for_missing_variable(self):
        """_try_variable_model returns None when named variable record does not exist."""
        if self.env.get("spp.cel.variable") is None:
            self.skipTest("spp_cel not installed")
        result = self.indicator_registry._try_variable_model("nonexistent_variable_xyz", self.registrants.ids)
        self.assertIsNone(result)
