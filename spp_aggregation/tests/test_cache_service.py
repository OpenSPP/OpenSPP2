# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields

from .common import AggregationTestCase


class TestCacheService(AggregationTestCase):
    """Test cache service for aggregation results."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.aggregation.cache"]

        # Create a test scope
        cls.test_scope = cls.env["spp.aggregation.scope"].create(
            {
                "name": "Test Cache Scope",
                "scope_type": "area",
                "area_id": cls.area_region.id,
                "include_child_areas": True,
            }
        )

    def test_cache_key_generation(self):
        """Test that cache keys are generated consistently."""
        statistics = ["count", "eligible_count"]
        group_by = ["gender", "disability_status"]

        # Generate key twice - should be same
        key1 = self.cache_service._generate_cache_key(self.test_scope, statistics, group_by)
        key2 = self.cache_service._generate_cache_key(self.test_scope, statistics, group_by)

        self.assertEqual(key1, key2, "Cache keys should be consistent")
        self.assertTrue(len(key1) == 64, "Cache key should be SHA256 hash (64 chars)")

        # Different statistics should produce different key
        key3 = self.cache_service._generate_cache_key(self.test_scope, ["count"], group_by)
        self.assertNotEqual(key1, key3, "Different statistics should produce different keys")

        # Different group_by should produce different key
        key4 = self.cache_service._generate_cache_key(self.test_scope, statistics, ["gender"])
        self.assertNotEqual(key1, key4, "Different group_by should produce different keys")

    def test_ttl_configuration(self):
        """Test TTL is correct for each scope type."""
        # Area scope - 1 hour
        ttl = self.cache_service._get_ttl_for_scope_type("area")
        self.assertEqual(ttl, 3600, "Area scope should have 1 hour TTL")

        # CEL scope - 15 minutes
        ttl = self.cache_service._get_ttl_for_scope_type("cel")
        self.assertEqual(ttl, 900, "CEL scope should have 15 minute TTL")

        # Spatial polygon - no cache
        ttl = self.cache_service._get_ttl_for_scope_type("spatial_polygon")
        self.assertEqual(ttl, 0, "Spatial polygon should have no cache")

        # Spatial buffer - no cache
        ttl = self.cache_service._get_ttl_for_scope_type("spatial_buffer")
        self.assertEqual(ttl, 0, "Spatial buffer should have no cache")

        # Area tag - 1 hour
        ttl = self.cache_service._get_ttl_for_scope_type("area_tag")
        self.assertEqual(ttl, 3600, "Area tag scope should have 1 hour TTL")

        # Explicit - 30 minutes
        ttl = self.cache_service._get_ttl_for_scope_type("explicit")
        self.assertEqual(ttl, 1800, "Explicit scope should have 30 minute TTL")

    def test_store_and_retrieve_cache(self):
        """Test storing and retrieving cached results."""
        statistics = ["count"]
        group_by = ["gender"]
        result = {
            "total_count": 100,
            "statistics": {"count": {"value": 100, "suppressed": False}},
            "breakdown": {
                "male": {"count": 60, "statistics": {}},
                "female": {"count": 40, "statistics": {}},
            },
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        # Store result
        stored = self.cache_service.store_result(self.test_scope, statistics, group_by, result)
        self.assertTrue(stored, "Result should be stored")

        # Retrieve result
        cached = self.cache_service.get_cached_result(self.test_scope, statistics, group_by)
        self.assertIsNotNone(cached, "Should retrieve cached result")
        self.assertTrue(cached["from_cache"], "Result should be marked as from cache")
        self.assertEqual(cached["total_count"], 100, "Cached data should match")

    def test_cache_disabled_for_spatial_queries(self):
        """Test that spatial queries are not cached."""
        # Create spatial polygon scope
        spatial_scope = self.env["spp.aggregation.scope"].create(
            {
                "name": "Test Spatial Scope",
                "scope_type": "spatial_polygon",
                "geometry_geojson": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    }
                ),
            }
        )

        result = {
            "total_count": 50,
            "statistics": {},
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        # Try to store - should return False (caching disabled)
        stored = self.cache_service.store_result(spatial_scope, [], [], result)
        self.assertFalse(stored, "Spatial queries should not be cached")

        # Try to retrieve - should return None
        cached = self.cache_service.get_cached_result(spatial_scope, [], [])
        self.assertIsNone(cached, "Should not retrieve cache for spatial queries")

    def test_cache_expiration(self):
        """Test that expired cache entries are not returned."""
        statistics = ["count"]
        group_by = []
        result = {
            "total_count": 100,
            "statistics": {"count": {"value": 100, "suppressed": False}},
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        # Store result
        self.cache_service.store_result(self.test_scope, statistics, group_by, result)

        # Verify it's cached
        cached = self.cache_service.get_cached_result(self.test_scope, statistics, group_by)
        self.assertIsNotNone(cached, "Should retrieve fresh cache")

        # Mock time to be 2 hours later (past TTL for area scope)
        future_time = fields.Datetime.now() + timedelta(hours=2)
        with patch("odoo.addons.spp_aggregation.models.service_cache.fields.Datetime.now") as mock_now:
            mock_now.return_value = future_time

            # Try to retrieve - should be expired
            cached = self.cache_service.get_cached_result(self.test_scope, statistics, group_by)
            self.assertIsNone(cached, "Expired cache should not be returned")

    def test_invalidate_scope(self):
        """Test invalidating all cache for a scope.

        Note: Currently this invalidates all entries of the same scope type
        (conservative approach).
        """
        # Store multiple results for the same scope type (area)
        result = {
            "total_count": 100,
            "statistics": {},
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        self.cache_service.store_result(self.test_scope, ["count"], [], result)
        self.cache_service.store_result(self.test_scope, ["count"], ["gender"], result)
        self.cache_service.store_result(self.test_scope, ["eligible_count"], [], result)

        # Verify all are cached
        self.assertIsNotNone(self.cache_service.get_cached_result(self.test_scope, ["count"], []))
        self.assertIsNotNone(self.cache_service.get_cached_result(self.test_scope, ["count"], ["gender"]))
        self.assertIsNotNone(self.cache_service.get_cached_result(self.test_scope, ["eligible_count"], []))

        # Invalidate scope (invalidates all entries of scope type)
        count = self.cache_service.invalidate_scope(self.test_scope)
        self.assertGreaterEqual(
            count, 3, "Should invalidate at least the 3 cache entries we created"
        )

        # Verify all are gone
        self.assertIsNone(self.cache_service.get_cached_result(self.test_scope, ["count"], []))
        self.assertIsNone(self.cache_service.get_cached_result(self.test_scope, ["count"], ["gender"]))
        self.assertIsNone(self.cache_service.get_cached_result(self.test_scope, ["eligible_count"], []))

    def test_invalidate_all(self):
        """Test invalidating all cache entries."""
        # Create multiple scopes and cache results
        scope1 = self.test_scope
        scope2 = self.env["spp.aggregation.scope"].create(
            {
                "name": "Test Scope 2",
                "scope_type": "area",
                "area_id": self.area_district.id,
                "include_child_areas": False,
            }
        )

        result = {
            "total_count": 100,
            "statistics": {},
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        self.cache_service.store_result(scope1, ["count"], [], result)
        self.cache_service.store_result(scope2, ["count"], [], result)

        # Verify both are cached
        self.assertIsNotNone(self.cache_service.get_cached_result(scope1, ["count"], []))
        self.assertIsNotNone(self.cache_service.get_cached_result(scope2, ["count"], []))

        # Invalidate all
        count = self.cache_service.invalidate_all()
        self.assertEqual(count, 2, "Should invalidate all cache entries")

        # Verify both are gone
        self.assertIsNone(self.cache_service.get_cached_result(scope1, ["count"], []))
        self.assertIsNone(self.cache_service.get_cached_result(scope2, ["count"], []))

    def test_cleanup_expired(self):
        """Test cleanup of expired cache entries."""
        statistics = ["count"]
        group_by = []
        result = {
            "total_count": 100,
            "statistics": {},
            "from_cache": False,
            "computed_at": fields.Datetime.now().isoformat(),
            "access_level": "aggregate",
        }

        # Store result
        self.cache_service.store_result(self.test_scope, statistics, group_by, result)

        # Manually update computed_at to be 2 hours ago
        entry = self.env["spp.aggregation.cache.entry"].search([], limit=1)
        old_time = fields.Datetime.now() - timedelta(hours=2)
        entry.write({"computed_at": old_time})

        # Run cleanup
        removed = self.cache_service.cleanup_expired()
        self.assertEqual(removed, 1, "Should remove 1 expired entry")

        # Verify entry is gone
        cached = self.cache_service.get_cached_result(self.test_scope, statistics, group_by)
        self.assertIsNone(cached, "Expired cache should be cleaned up")
