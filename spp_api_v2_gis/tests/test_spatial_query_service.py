# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spatial query service with CEL statistics integration."""

from datetime import date

from odoo.tests.common import TransactionCase


class TestSpatialQueryService(TransactionCase):
    """Test spatial query service functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test District",
                "code": "TEST-DIST-001",
            }
        )

        # Create test group (household)
        cls.group = cls.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

        # Create test individuals (members)
        cls.member_adult_male = cls.env["res.partner"].create(
            {
                "name": "Adult Male",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
                "birthdate": date(1985, 1, 15),  # ~40 years old
            }
        )

        cls.member_adult_female = cls.env["res.partner"].create(
            {
                "name": "Adult Female",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
                "birthdate": date(1990, 6, 20),  # ~35 years old
            }
        )

        cls.member_child = cls.env["res.partner"].create(
            {
                "name": "Child",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
                "birthdate": date(2015, 3, 10),  # ~10 years old
            }
        )

        cls.member_elderly = cls.env["res.partner"].create(
            {
                "name": "Elderly",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
                "birthdate": date(1960, 9, 5),  # ~65 years old
            }
        )

        # Add members to group via group_membership_ids
        if "spp.group.membership" in cls.env:
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.group.id,
                    "individual": cls.member_adult_male.id,
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.group.id,
                    "individual": cls.member_adult_female.id,
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.group.id,
                    "individual": cls.member_child.id,
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.group.id,
                    "individual": cls.member_elderly.id,
                }
            )

    def test_service_initialization(self):
        """Test that spatial query service can be initialized."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)
        self.assertIsNotNone(service)
        self.assertEqual(service.env, self.env)

    def test_compute_statistics_uses_unified_aggregation(self):
        """Test statistics computation through the aggregation engine."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Get IDs of all registrants
        registrant_ids = [
            self.group.id,
            self.member_adult_male.id,
            self.member_adult_female.id,
            self.member_child.id,
            self.member_elderly.id,
        ]

        # Compute statistics via aggregation service
        result = service._compute_statistics(registrant_ids, [])

        # Should return dict with statistics and metadata
        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)
        self.assertIsInstance(result["statistics"], dict)

    def test_empty_statistics(self):
        """Test that empty registrant list returns empty statistics."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Compute statistics for empty list
        result = service._compute_statistics([], [])

        # Should return dict with empty statistics
        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)
        self.assertIsInstance(result["statistics"], dict)

    def test_statistic_model_exists(self):
        """Test that spp.indicator model exists and has required fields."""
        Statistic = self.env["spp.indicator"]

        # Check that required fields exist
        self.assertIn("name", Statistic._fields)
        self.assertIn("label", Statistic._fields)
        self.assertIn("variable_id", Statistic._fields)
        self.assertIn("is_published_gis", Statistic._fields)
        self.assertIn("is_published_dashboard", Statistic._fields)
        self.assertIn("category_id", Statistic._fields)

    def test_create_gis_published_statistic(self):
        """Test creating a statistic published to GIS context."""
        Statistic = self.env["spp.indicator"]
        CelVariable = self.env["spp.cel.variable"]

        # Create a CEL variable
        var = CelVariable.create(
            {
                "name": "test_gis_stat_var",
                "cel_accessor": "test_gis_stat",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        # Create a statistic that publishes the variable to GIS
        stat = Statistic.create(
            {
                "name": "test_gis_stat",
                "label": "Test GIS Stat",
                "variable_id": var.id,
                "format": "count",
                "is_published_gis": True,
            }
        )

        self.assertTrue(stat.is_published_gis)
        self.assertEqual(stat.label, "Test GIS Stat")
        self.assertEqual(stat.format, "count")
        self.assertEqual(stat.variable_id, var)

    def test_get_published_for_gis_context(self):
        """Test querying statistics published to GIS context."""
        Statistic = self.env["spp.indicator"]
        CelVariable = self.env["spp.cel.variable"]

        # Create a CEL variable
        var = CelVariable.create(
            {
                "name": "test_context_var",
                "cel_accessor": "test_context",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "boolean",
                "state": "active",
            }
        )

        # Create GIS-published statistic
        gis_stat = Statistic.create(
            {
                "name": "gis_published_stat",
                "label": "GIS Published",
                "variable_id": var.id,
                "is_published_gis": True,
            }
        )

        # Create non-GIS statistic
        dashboard_stat = Statistic.create(
            {
                "name": "dashboard_only_stat",
                "label": "Dashboard Only",
                "variable_id": var.id,
                "is_published_dashboard": True,
                "is_published_gis": False,
            }
        )

        # Query GIS statistics
        gis_stats = Statistic.get_published_for_context("gis")

        self.assertIn(gis_stat, gis_stats)
        self.assertNotIn(dashboard_stat, gis_stats)

    def test_statistics_with_published_statistics(self):
        """Test computing GIS-published statistics through aggregation service."""
        from ..services.spatial_query_service import SpatialQueryService

        CelVariable = self.env["spp.cel.variable"]
        Statistic = self.env["spp.indicator"]

        # Create a CEL variable for counting groups
        var = CelVariable.create(
            {
                "name": "test_household_count",
                "cel_accessor": "household_count",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        # Create a statistic that publishes the variable to GIS
        Statistic.create(
            {
                "name": "household_count",
                "label": "Household Count",
                "variable_id": var.id,
                "format": "count",
                "is_published_gis": True,
            }
        )

        service = SpatialQueryService(self.env)

        # Compute statistics - should use GIS-published statistics
        result = service._compute_statistics([self.group.id], [])

        # Should have the household_count statistic
        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)
        # If statistics are found and evaluated, they should be in the result
        if "household_count" in result["statistics"]:
            self.assertIsNotNone(result["statistics"]["household_count"])

    def test_compute_statistics_unknown_statistic(self):
        """Test that unknown statistics return a valid response shape."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Requesting non-existent statistics should still return a valid dict.
        registrant_ids = [self.group.id]
        result = service._compute_statistics(registrant_ids, ["nonexistent_variable_xyz"])

        # Should return valid dict with statistics and metadata
        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)

    def test_suppression_precedence_uses_stricter_threshold(self):
        """Test suppression precedence: effective k = max(user_k, stat/context_k)."""
        from ..services.spatial_query_service import SpatialQueryService

        CelVariable = self.env["spp.cel.variable"]
        Statistic = self.env["spp.indicator"]

        # User rule sets k=10
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "GIS Test Rule k10",
                "access_level": "aggregate",
                "user_id": self.env.user.id,
                "minimum_k_anonymity": 10,
                "allow_inline_scopes": True,
            }
        )

        # Statistic asks for lower k=2; effective should still be 10.
        variable = CelVariable.create(
            {
                "name": "suppression_precedence_var",
                "cel_accessor": "suppression_precedence_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        Statistic.create(
            {
                "name": "suppression_precedence_stat",
                "label": "Suppression Precedence Stat",
                "variable_id": variable.id,
                "format": "count",
                "minimum_count": 2,
                "is_published_gis": True,
            }
        )

        service = SpatialQueryService(self.env)
        registrant_ids = [
            self.group.id,
            self.member_adult_male.id,
            self.member_adult_female.id,
            self.member_child.id,
            self.member_elderly.id,
        ]  # 5 records < effective k=10

        result = service._compute_statistics(registrant_ids, ["suppression_precedence_stat"])
        self.assertIn("statistics", result)
        self.assertIn("suppression_precedence_stat", result["statistics"])
        self.assertEqual(result["statistics"]["suppression_precedence_stat"], "<10")


class TestSpatialQueryServicePublicUser(TransactionCase):
    """Tests for spatial query service running as public user.

    The GIS API endpoints run as base.public_user. The service must work
    in this context because aggregation service and scope resolver use
    sudo() internally for config/data reads.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.public_user = cls.env.ref("base.public_user")

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Public User Test District",
                "code": "PUB-DIST-001",
            }
        )

        cls.group = cls.env["res.partner"].create(
            {
                "name": "Public User Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Public User Test Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area.id,
            }
        )

    def test_compute_statistics_in_public_user_context(self):
        """Test that _compute_statistics works for public user."""
        from ..services.spatial_query_service import SpatialQueryService

        public_env = self.env(user=self.public_user)
        service = SpatialQueryService(public_env)

        registrant_ids = [self.group.id, self.individual.id]
        result = service._compute_statistics(registrant_ids, [])

        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)

    def test_convert_aggregation_result_without_partner_browse(self):
        """Test that _convert_aggregation_result works without browsing partners."""
        from ..services.spatial_query_service import SpatialQueryService

        public_env = self.env(user=self.public_user)
        service = SpatialQueryService(public_env)

        # Simulate aggregation result with metadata
        agg_result = {
            "statistics": {},
            "total_count": 2,
            "access_level": "aggregate",
            "from_cache": False,
            "computed_at": "2024-01-01T00:00:00Z",
        }

        result = service._convert_aggregation_result(agg_result, [self.group.id, self.individual.id])
        self.assertIsInstance(result, dict)
        self.assertIn("statistics", result)
        self.assertIn("access_level", result)
        self.assertIn("from_cache", result)
        self.assertIn("computed_at", result)
        self.assertEqual(result["access_level"], "aggregate")
        self.assertFalse(result["from_cache"])
        self.assertEqual(result["computed_at"], "2024-01-01T00:00:00Z")


class TestSpatialQueryServiceMetadata(TransactionCase):
    """Tests for privacy metadata in spatial query responses."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Metadata Test District",
                "code": "META-DIST-001",
            }
        )

        cls.group = cls.env["res.partner"].create(
            {
                "name": "Metadata Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

    def test_query_statistics_includes_metadata(self):
        """Test that query_statistics includes privacy metadata."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Use a simple polygon geometry
        geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }

        result = service.query_statistics(geometry=geometry, filters=None, variables=None)

        # Verify metadata fields are present
        self.assertIn("access_level", result)
        self.assertIn("from_cache", result)
        self.assertIn("computed_at", result)

        # Verify metadata types
        if result["access_level"] is not None:
            self.assertIsInstance(result["access_level"], str)
        self.assertIsInstance(result["from_cache"], bool)
        if result["computed_at"] is not None:
            self.assertIsInstance(result["computed_at"], str)

    def test_convert_aggregation_result_preserves_suppressed_flags(self):
        """Test that per-statistic suppressed flags are preserved."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Simulate aggregation result with suppressed statistics
        agg_result = {
            "statistics": {
                "total_households": {"value": "<10", "suppressed": True},
                "total_individuals": {"value": 42, "suppressed": False},
            },
            "access_level": "aggregate",
            "from_cache": False,
            "computed_at": "2024-01-01T00:00:00Z",
        }

        result = service._convert_aggregation_result(agg_result, [self.group.id])

        # Check that suppressed flags are preserved in the grouped stats
        self.assertIn("_grouped", result["statistics"])
        # The structure should preserve suppressed flags in the grouped format
        for category_stats in result["statistics"]["_grouped"].values():
            for stat_entry in category_stats.values():
                self.assertIn("suppressed", stat_entry)

    def test_metadata_defaults_to_none_when_missing(self):
        """Test that metadata fields default to None/False when not provided."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Simulate aggregation result without metadata
        agg_result = {
            "statistics": {},
        }

        result = service._convert_aggregation_result(agg_result, [self.group.id])

        # Verify defaults
        self.assertIsNone(result["access_level"])
        self.assertFalse(result["from_cache"])
        self.assertIsNone(result["computed_at"])


class TestSpatialQueryCountSuppression(TransactionCase):
    """k-anonymity suppression of registrant counts (location/presence leak fix)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Area with no geo_polygon -> spatial queries match nobody (count 0),
        # which must still be reported as suppressed (indistinguishable from small).
        cls.area = cls.env["spp.area"].create({"draft_name": "Suppression Test District", "code": "SUP-DIST-001"})

    def _service(self):
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)

    def test_apply_suppression_canonicalizes_below_k(self):
        """A below-k result collapses to a fixed canonical form; >=k is untouched.

        The canonical form must be identical for a genuinely empty region (0) and
        a small one (1..k-1): floored count AND blanked people-correlated metadata
        (statistics, access_level, from_cache, computed_at, query_method,
        areas_matched). Otherwise those fields reconstruct the presence bit.
        """
        service = self._service()
        k = 5

        def populated(count, method):
            return {
                "total_count": count,
                "query_method": method,
                "areas_matched": 3,
                "statistics": {"total_individuals": 2},
                "access_level": "aggregate",
                "from_cache": True,
                "computed_at": "2024-01-01T00:00:00Z",
            }

        empty = service._apply_suppression(populated(0, "area_fallback"), k)
        small = service._apply_suppression(populated(3, "coordinates"), k)
        canonical = {
            "total_count": 0,
            "count_suppressed": True,
            "query_method": "suppressed",
            "areas_matched": 0,
            "statistics": {},
            "access_level": None,
            "from_cache": False,
            "computed_at": None,
        }
        # Empty and small must be byte-identical (no field distinguishes them).
        self.assertEqual(empty, canonical)
        self.assertEqual(small, canonical)

        # A count at/above the threshold is untouched except for the flag.
        big = service._apply_suppression(populated(10, "coordinates"), k)
        self.assertEqual(big["total_count"], 10)
        self.assertFalse(big["count_suppressed"])
        self.assertEqual(big["query_method"], "coordinates")
        self.assertEqual(big["statistics"], {"total_individuals": 2})

    def test_get_k_threshold_default(self):
        """With no access rule, the privacy-service default threshold applies."""
        default_k = self.env["spp.metric.privacy"].DEFAULT_K_THRESHOLD
        self.assertEqual(self._service()._get_k_threshold(), default_k)

    def test_get_k_threshold_reads_access_rule(self):
        """The caller's access-rule minimum_k_anonymity is used."""
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "GIS Count Rule k9",
                "access_level": "aggregate",
                "user_id": self.env.user.id,
                "minimum_k_anonymity": 9,
                "allow_inline_scopes": True,
            }
        )
        self.assertEqual(self._service()._get_k_threshold(), 9)

    def _assert_canonical_suppressed(self, result):
        """The response must not carry any people-correlated field that could
        distinguish a small region from an empty one."""
        self.assertEqual(result["total_count"], 0)
        self.assertTrue(result["count_suppressed"])
        self.assertEqual(result["statistics"], {})
        self.assertIsNone(result["access_level"])
        self.assertFalse(result["from_cache"])
        self.assertIsNone(result["computed_at"])
        self.assertEqual(result["query_method"], "suppressed")
        self.assertEqual(result["areas_matched"], 0)

    def test_query_statistics_suppresses_small_result(self):
        """query_statistics returns the canonical suppressed response below threshold."""
        geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        result = self._service().query_statistics(geometry=geometry, filters=None, variables=None)
        self._assert_canonical_suppressed(result)

    def test_batch_suppresses_items_and_summary(self):
        """Batch per-geometry results and the summary both carry suppression."""
        geometries = [
            {"id": "a", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}},
        ]
        result = self._service().query_statistics_batch(geometries=geometries, filters=None, variables=None)
        self.assertTrue(result["summary"]["count_suppressed"])
        self.assertEqual(result["summary"]["total_count"], 0)
        self.assertEqual(result["summary"]["statistics"], {})
        self.assertIsNone(result["summary"]["access_level"])
        self.assertIsNone(result["summary"]["computed_at"])
        self._assert_canonical_suppressed(result["results"][0])

    def test_proximity_suppresses_small_result(self):
        """query_proximity returns the canonical suppressed response below threshold."""
        result = self._service().query_proximity(
            reference_points=[{"longitude": 0.5, "latitude": 0.5}],
            radius_km=1.0,
            relation="within",
            filters=None,
            variables=None,
        )
        self._assert_canonical_suppressed(result)
