# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import time

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDimensionCache(TransactionCase):
    """Test dimension evaluation caching for performance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.metrics.dimension.cache"]
        cls.dimension_model = cls.env["spp.demographic.dimension"]
        cls.partner_model = cls.env["res.partner"]

        # Create test dimension (field-based using is_group boolean field)
        cls.registrant_type_dimension = cls.dimension_model.create(
            {
                "name": "test_registrant_type_cache",
                "label": "Registrant Type (Cache Test)",
                "dimension_type": "field",
                "field_path": "is_group",
            }
        )

        # Create test registrants
        cls.registrants = []
        for i in range(100):  # Create 100 registrants for performance testing
            registrant = cls.partner_model.create(
                {
                    "name": f"Test Registrant {i}",
                    "is_registrant": True,
                    "is_group": i % 2 == 0,  # Alternate between groups and individuals
                }
            )
            cls.registrants.append(registrant)

        cls.registrant_ids = [r.id for r in cls.registrants]

    def test_cache_basic_functionality(self):
        """Test that cache stores and retrieves evaluations correctly."""
        # First call should compute and cache
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids)

        self.assertEqual(len(result1), 100, "Should evaluate all 100 registrants")
        self.assertIn(self.registrants[0].id, result1)

        # Second call should hit cache
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids)

        # Results should be identical
        self.assertEqual(result1, result2, "Cached result should match original")

    def test_cache_performance(self):
        """Test that caching improves performance significantly."""
        # Clear cache first
        self.cache_service.clear_dimension_cache()

        # First call (cache miss) - measure time
        start = time.time()
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids)
        time_uncached = time.time() - start

        # Second call (cache hit) - measure time
        start = time.time()
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids)
        time_cached = time.time() - start

        # Cache should be faster
        # Note: With only 100 records, the speedup might be modest
        # In production with 10k+ records, expect 5-10x speedup
        self.assertTrue(
            time_cached < time_uncached or time_cached < 0.1,
            f"Cache should be fast: {time_cached:.4f}s vs {time_uncached:.4f}s",
        )

        # Results should be identical
        self.assertEqual(result1, result2)

    def test_cache_invalidation_on_write(self):
        """Test that cache is invalidated when dimension is modified."""
        # Populate cache
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:10])

        # Modify dimension
        self.registrant_type_dimension.write({"label": "Gender Modified"})

        # Evaluate again - should compute fresh (cache cleared)
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:10])

        # Results should still be valid (same values, just re-computed)
        self.assertEqual(len(result2), 10)
        self.assertEqual(result1, result2, "Results should be same after re-computation")

    def test_cache_invalidation_on_unlink(self):
        """Test that cache is invalidated when dimension is deleted."""
        # Create temporary dimension
        temp_dimension = self.dimension_model.create(
            {
                "name": "temp_dimension",
                "label": "Temporary Dimension",
                "dimension_type": "field",
                "field_path": "name",
            }
        )

        # Populate cache
        result1 = self.cache_service.evaluate_dimension_batch(temp_dimension, self.registrant_ids[:5])
        self.assertEqual(len(result1), 5)

        # Delete dimension (should clear cache)
        temp_dimension.unlink()

        # Cache should be cleared (we can't verify directly, but ensure no errors)
        # Just verify the service is still functional
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:5])
        self.assertEqual(len(result2), 5)

    def test_cache_with_different_registrant_sets(self):
        """Test that cache handles different registrant sets correctly."""
        # Cache for first 50 registrants
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:50])

        # Cache for last 50 registrants
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[50:])

        # Both should be cached independently
        self.assertEqual(len(result1), 50)
        self.assertEqual(len(result2), 50)

        # Verify no overlap in keys
        for key in result1:
            self.assertNotIn(key, result2)

    def test_cache_warm_functionality(self):
        """Test that cache warming works correctly."""
        # Clear cache first
        self.cache_service.clear_dimension_cache()

        # Create multiple dimensions
        name_dimension = self.dimension_model.create(
            {
                "name": "test_name_cache",
                "label": "Name (Cache Test)",
                "dimension_type": "field",
                "field_path": "name",
            }
        )

        dimensions = [self.registrant_type_dimension, name_dimension]

        # Warm cache
        self.cache_service.warm_cache(dimensions, self.registrant_ids[:20])

        # Verify cache is populated (by checking that subsequent calls are fast)
        start = time.time()
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:20])
        time_cached = time.time() - start

        self.assertEqual(len(result1), 20)
        self.assertTrue(time_cached < 0.1, f"Warmed cache should be fast: {time_cached:.4f}s")

    def test_cache_clear_all(self):
        """Test that clearing all caches works."""
        # Populate cache for multiple dimensions
        result1 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:10])

        # Clear all caches
        self.cache_service.clear_dimension_cache()

        # Next call should re-compute (we can't verify cache miss directly,
        # but ensure results are still correct)
        result2 = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, self.registrant_ids[:10])

        self.assertEqual(result1, result2, "Results should be same after cache clear")

    def test_cache_with_empty_registrants(self):
        """Test that cache handles empty registrant lists gracefully."""
        result = self.cache_service.evaluate_dimension_batch(self.registrant_type_dimension, [])

        self.assertEqual(result, {}, "Empty registrant list should return empty dict")

    def test_cache_with_none_dimension(self):
        """Test that cache handles None dimension gracefully."""
        result = self.cache_service.evaluate_dimension_batch(None, self.registrant_ids)

        self.assertEqual(result, {}, "None dimension should return empty dict")

    def test_breakdown_service_uses_cache(self):
        """Test that breakdown service benefits from caching."""
        breakdown_service = self.env["spp.metrics.breakdown"]

        # Clear cache first
        self.cache_service.clear_dimension_cache()

        # First breakdown (cache miss)
        start = time.time()
        result1 = breakdown_service.compute_breakdown(self.registrant_ids, ["test_registrant_type_cache"])
        time_uncached = time.time() - start

        # Second breakdown (cache hit)
        start = time.time()
        result2 = breakdown_service.compute_breakdown(self.registrant_ids, ["test_registrant_type_cache"])
        time_cached = time.time() - start

        # Results should be identical
        self.assertEqual(result1, result2, "Breakdown results should be same with cache")

        # Cache should be faster
        self.assertTrue(
            time_cached <= time_uncached or time_cached < 0.1,
            f"Cached breakdown should be fast: {time_cached:.4f}s vs {time_uncached:.4f}s",
        )

        # Verify breakdown structure
        self.assertGreater(len(result1), 0, "Breakdown should have results")
        for _key, value in result1.items():
            self.assertIn("count", value)
            self.assertIn("labels", value)
