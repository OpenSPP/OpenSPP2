# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extended coverage tests for spp_analytics module.

Covers edge cases in access rules, cache key generation,
scope resolver, and aggregation service convenience methods.
"""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

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
