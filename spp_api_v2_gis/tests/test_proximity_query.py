# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for proximity query service.

These tests cover validation, area fallback, metadata, and statistics.
Coordinate-based tests require spp_registrant_gis (adds coordinates
field to res.partner), which is not a direct dependency of spp_api_v2_gis.
Area fallback tests work with the base spp_gis module (provides
geo_polygon on spp.area).
"""

import json

from odoo.tests.common import TransactionCase


class TestProximityQueryValidation(TransactionCase):
    """Test input validation in query_proximity()."""

    @classmethod
    def setUpClass(cls):
        """Set up minimal test data."""
        super().setUpClass()
        cls.reference_points = [{"longitude": 28.0, "latitude": -2.0}]

    def _get_service(self):
        """Create a SpatialQueryService instance."""
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)

    def test_empty_reference_points_raises(self):
        """Test that empty reference points raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.query_proximity(
                reference_points=[],
                radius_km=5.0,
                relation="within",
            )

    def test_zero_radius_raises(self):
        """Test that zero radius raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.query_proximity(
                reference_points=self.reference_points,
                radius_km=0,
                relation="within",
            )

    def test_negative_radius_raises(self):
        """Test that negative radius raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.query_proximity(
                reference_points=self.reference_points,
                radius_km=-5.0,
                relation="within",
            )

    def test_invalid_relation_raises(self):
        """Test that invalid relation raises ValueError."""
        service = self._get_service()

        with self.assertRaises(ValueError):
            service.query_proximity(
                reference_points=self.reference_points,
                radius_km=5.0,
                relation="overlapping",
            )


class TestProximityQueryAreaFallback(TransactionCase):
    """Test proximity query with area fallback.

    When spp_registrant_gis is not installed (no coordinates field on
    res.partner), the service falls back to area-based proximity.
    This test class sets up areas with geo_polygon data and verifies
    that the area fallback path works correctly.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data with area polygons.

        Test geography (approximate locations in East Africa):
        - Reference point (health center): lon=28.0, lat=-2.0
        - Near area: small polygon around 28.0, -2.0 (~10 km extent)
        - Far area: small polygon around 32.0, -5.0 (~500 km away)
        """
        super().setUpClass()

        # Create area with polygon near reference point
        cls.area_near = cls.env["spp.area"].create(
            {
                "draft_name": "Proximity Near Area",
                "code": "PROX-NEAR-001",
            }
        )
        near_polygon = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[27.95, -2.05], [28.05, -2.05], [28.05, -1.95], [27.95, -1.95], [27.95, -2.05]]],
            }
        )
        cls.env.cr.execute(
            """
            UPDATE spp_area
            SET geo_polygon = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
            WHERE id = %s
            """,
            [near_polygon, cls.area_near.id],
        )

        # Create area far from reference point
        cls.area_far = cls.env["spp.area"].create(
            {
                "draft_name": "Proximity Far Area",
                "code": "PROX-FAR-001",
            }
        )
        far_polygon = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[31.95, -5.05], [32.05, -5.05], [32.05, -4.95], [31.95, -4.95], [31.95, -5.05]]],
            }
        )
        cls.env.cr.execute(
            """
            UPDATE spp_area
            SET geo_polygon = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
            WHERE id = %s
            """,
            [far_polygon, cls.area_far.id],
        )

        # Partners in near area
        cls.partner_near = cls.env["res.partner"].create(
            {
                "name": "Near Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_near.id,
            }
        )

        cls.group_near = cls.env["res.partner"].create(
            {
                "name": "Near Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_near.id,
            }
        )

        # Partner in far area
        cls.partner_far = cls.env["res.partner"].create(
            {
                "name": "Far Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_far.id,
            }
        )

        cls.reference_points = [{"longitude": 28.0, "latitude": -2.0}]

    def _get_service(self):
        """Create a SpatialQueryService instance."""
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)

    def test_within_returns_registrants_in_nearby_areas(self):
        """Test 'within' via area fallback returns registrants in areas near ref points."""
        service = self._get_service()

        # 20 km radius should cover the near area polygon
        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
        )

        self.assertIn("total_count", result)
        self.assertIn("registrant_ids", result)
        # The near area holds fewer than the k-anonymity threshold of registrants,
        # so the exact count is suppressed to 0 with the flag set. Matching is still
        # verified below via registrant_ids (the router strips that field from the
        # API response; suppression only affects the disclosed count).
        self.assertEqual(result["total_count"], 0)
        self.assertTrue(result["count_suppressed"])

        # Near partner should be in the result (either via coordinates or area fallback)
        self.assertIn(self.partner_near.id, result["registrant_ids"])

        # Far partner should NOT be within 20 km
        self.assertNotIn(self.partner_far.id, result["registrant_ids"])

    def test_beyond_returns_registrants_in_far_areas(self):
        """Test 'beyond' via area fallback returns registrants in areas far from ref points."""
        service = self._get_service()

        # 20 km radius: far area (~500 km away) should be beyond
        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="beyond",
        )

        self.assertIn("total_count", result)
        self.assertIn("registrant_ids", result)

        # Far partner should be beyond 20 km
        self.assertIn(self.partner_far.id, result["registrant_ids"])

        # Near partner should NOT be beyond 20 km
        self.assertNotIn(self.partner_near.id, result["registrant_ids"])

    def test_large_radius_includes_all_areas(self):
        """Test that a large radius includes all areas."""
        service = self._get_service()

        # 1000 km radius should cover everything (~554 km to far area)
        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=1000.0,
            relation="within",
        )

        # Both near and far should be included
        self.assertIn(self.partner_near.id, result["registrant_ids"])
        self.assertIn(self.partner_far.id, result["registrant_ids"])

    def test_is_group_filter(self):
        """Test that is_group filter works with area fallback."""
        service = self._get_service()

        # Filter to groups only within 20 km
        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
            filters={"is_group": True},
        )

        # Group should be in the result
        self.assertIn(self.group_near.id, result["registrant_ids"])
        # Individual should NOT be in the result
        self.assertNotIn(self.partner_near.id, result["registrant_ids"])

    def test_is_group_false_filter(self):
        """Test that is_group=False filter returns only individuals."""
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
            filters={"is_group": False},
        )

        # Individual should be in the result
        self.assertIn(self.partner_near.id, result["registrant_ids"])
        # Group should NOT be in the result
        self.assertNotIn(self.group_near.id, result["registrant_ids"])

    def test_multiple_reference_points(self):
        """Test with multiple reference points covering different areas."""
        service = self._get_service()

        # Two reference points: one near each area
        multi_refs = [
            {"longitude": 28.0, "latitude": -2.0},  # Near the near area
            {"longitude": 32.0, "latitude": -5.0},  # Near the far area
        ]

        result = service.query_proximity(
            reference_points=multi_refs,
            radius_km=20.0,
            relation="within",
        )

        # Both should be within 20 km of at least one reference point
        self.assertIn(self.partner_near.id, result["registrant_ids"])
        self.assertIn(self.partner_far.id, result["registrant_ids"])

    def test_statistics_computed(self):
        """Test that statistics are computed for matched registrants."""
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
            variables=[],
        )

        # Statistics metadata should be present
        self.assertIn("statistics", result)
        self.assertIsInstance(result["statistics"], dict)
        self.assertIn("access_level", result)
        self.assertIn("from_cache", result)
        self.assertIn("computed_at", result)

    def test_reference_points_count_in_result(self):
        """Test that result includes the reference points count."""
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
        )

        self.assertEqual(result["reference_points_count"], 1)

    def test_radius_km_in_result(self):
        """Test that result echoes back the radius."""
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=12.5,
            relation="within",
        )

        self.assertEqual(result["radius_km"], 12.5)

    def test_relation_in_result(self):
        """Test that result echoes back the relation."""
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="beyond",
        )

        self.assertEqual(result["relation"], "beyond")

    def test_areas_matched_count(self):
        """Test areas_matched reporting under k-anonymity suppression.

        The near area holds fewer than the k-anonymity threshold of registrants,
        so the whole response is canonicalized: query_method becomes "suppressed"
        and areas_matched is zeroed (it must not reveal that a small population's
        area was matched). Matching itself is verified in the other tests via
        registrant_ids.
        """
        service = self._get_service()

        result = service.query_proximity(
            reference_points=self.reference_points,
            radius_km=20.0,
            relation="within",
        )

        self.assertTrue(result["count_suppressed"])
        self.assertEqual(result["query_method"], "suppressed")
        self.assertEqual(result["areas_matched"], 0)
