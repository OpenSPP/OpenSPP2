# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for batch spatial query service."""

import json
from datetime import date

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

# Polygon covering roughly lon 27.9..28.1 / lat -2.1..-1.9 (East Africa).
QUERY_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[27.9, -2.1], [28.1, -2.1], [28.1, -1.9], [27.9, -1.9], [27.9, -2.1]]],
}


class TestBatchSpatialQueryService(TransactionCase):
    """Test batch spatial query service functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create two test areas with distinct registrants
        cls.area_1 = cls.env["spp.area"].create(
            {
                "draft_name": "Batch Test District 1",
                "code": "BATCH-DIST-001",
            }
        )
        cls.area_2 = cls.env["spp.area"].create(
            {
                "draft_name": "Batch Test District 2",
                "code": "BATCH-DIST-002",
            }
        )

        # Registrants in area 1
        cls.group_1 = cls.env["res.partner"].create(
            {
                "name": "Batch Household 1",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_1.id,
            }
        )
        cls.individual_1 = cls.env["res.partner"].create(
            {
                "name": "Batch Individual 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_1.id,
                "birthdate": date(1990, 5, 15),
            }
        )

        # Registrants in area 2
        cls.group_2 = cls.env["res.partner"].create(
            {
                "name": "Batch Household 2",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_2.id,
            }
        )
        cls.individual_2 = cls.env["res.partner"].create(
            {
                "name": "Batch Individual 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_2.id,
                "birthdate": date(2000, 8, 20),
            }
        )

    def test_batch_query_returns_per_geometry_results(self):
        """Test that batch query returns individual results for each geometry."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Use the simple geometry format that would be sent from the plugin
        geometries = [
            {
                "id": "zone_1",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "id": "zone_2",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
                },
            },
        ]

        result = service.query_statistics_batch(
            geometries=geometries,
            filters=None,
            variables=None,
        )

        # Verify structure
        self.assertIn("results", result)
        self.assertIn("summary", result)
        self.assertEqual(len(result["results"]), 2)

        # Each result should have the expected fields including metadata
        for item in result["results"]:
            self.assertIn("id", item)
            self.assertIn("total_count", item)
            self.assertIn("query_method", item)
            self.assertIn("areas_matched", item)
            self.assertIn("statistics", item)
            self.assertIn("access_level", item)
            self.assertIn("from_cache", item)
            self.assertIn("computed_at", item)

        # IDs should match request
        result_ids = {r["id"] for r in result["results"]}
        self.assertEqual(result_ids, {"zone_1", "zone_2"})

    def test_batch_query_summary_aggregation(self):
        """Test that batch query summary aggregates results."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        geometries = [
            {
                "id": "area_a",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
        ]

        result = service.query_statistics_batch(geometries=geometries)

        summary = result["summary"]
        self.assertIn("total_count", summary)
        self.assertIn("geometries_queried", summary)
        self.assertIn("statistics", summary)
        self.assertIn("access_level", summary)
        self.assertIn("from_cache", summary)
        self.assertIn("computed_at", summary)
        self.assertEqual(summary["geometries_queried"], 1)

    def test_batch_query_handles_invalid_geometry(self):
        """Test that batch query handles errors for individual geometries."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # Mix valid and invalid geometries
        geometries = [
            {
                "id": "valid",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "id": "invalid",
                "geometry": {"type": "InvalidType", "coordinates": []},
            },
        ]

        # Should not raise - individual errors are caught
        result = service.query_statistics_batch(geometries=geometries)

        self.assertEqual(len(result["results"]), 2)

        # The invalid geometry should return error/empty result
        invalid_result = next(r for r in result["results"] if r["id"] == "invalid")
        self.assertEqual(invalid_result["total_count"], 0)

    def test_batch_query_with_variables(self):
        """Test batch query passes variables to individual queries."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        geometries = [
            {
                "id": "test",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
        ]

        # Passing nonexistent variables should still return a valid response
        result = service.query_statistics_batch(
            geometries=geometries,
            variables=["nonexistent_var"],
        )

        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)

    def test_batch_query_with_filters(self):
        """Test batch query passes filters to individual queries."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        geometries = [
            {
                "id": "filtered",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
        ]

        result = service.query_statistics_batch(
            geometries=geometries,
            filters={"is_group": True},
        )

        self.assertIn("results", result)
        self.assertEqual(len(result["results"]), 1)

    def test_batch_query_empty_geometries_list(self):
        """Test batch query with empty geometries returns empty results."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        result = service.query_statistics_batch(geometries=[])

        self.assertEqual(len(result["results"]), 0)
        self.assertEqual(result["summary"]["total_count"], 0)
        self.assertEqual(result["summary"]["geometries_queried"], 0)


class TestBatchQueryDoesNotPoisonLaterGeometries(TransactionCase):
    """A geometry that fails inside PostgreSQL must not abort the rest of the batch.

    ``query_statistics`` only wraps its coordinate attempt in a savepoint; the
    area fallback it calls into runs raw SQL unguarded. If that fallback hits a
    genuine database error (not a Python-level ``ValueError``), the whole
    transaction is left aborted, and every later geometry in the same batch
    call fails too, since even opening a new savepoint requires a live
    transaction.
    """

    @classmethod
    def setUpClass(cls):
        """Create an area covering the query polygon plus a registrant in it."""
        super().setUpClass()

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Batch Poison Test Area",
                "code": "BATCH-POISON-001",
            }
        )
        cls.env.cr.execute(
            """
            UPDATE spp_area
            SET geo_polygon = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
            WHERE id = %s
            """,
            [json.dumps(QUERY_POLYGON), cls.area.id],
        )

        cls.group = cls.env["res.partner"].create(
            {
                "name": "Batch Poison Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

    def test_invalid_geometry_does_not_abort_later_geometries(self):
        """A DB-level failure on one geometry must not poison the geometries after it."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        geometries = [
            {
                "id": "invalid",
                # Genuinely invalid GeoJSON: ST_GeomFromGeoJSON rejects the type at
                # the database level, so this fails the same way a real bad request
                # would, rather than being simulated with a mock.
                "geometry": {"type": "InvalidType", "coordinates": []},
            },
            {
                "id": "valid",
                "geometry": QUERY_POLYGON,
            },
        ]

        with mute_logger("odoo.sql_db"):
            result = service.query_statistics_batch(geometries=geometries)

        self.assertEqual(len(result["results"]), 2)

        invalid_result = next(r for r in result["results"] if r["id"] == "invalid")
        self.assertEqual(invalid_result["query_method"], "error")

        valid_result = next(r for r in result["results"] if r["id"] == "valid")
        self.assertEqual(
            valid_result["query_method"],
            "area_fallback",
            "a DB error on an earlier geometry aborted the transaction for the rest of the batch",
        )
        self.assertEqual(valid_result["total_count"], 1)
        self.assertEqual(valid_result["areas_matched"], 1)


class TestBatchSpatialQuerySchemas(TransactionCase):
    """Test batch query Pydantic schemas."""

    def test_batch_request_schema(self):
        """Test BatchSpatialQueryRequest accepts valid input."""
        from ..schemas.query import BatchSpatialQueryRequest

        request = BatchSpatialQueryRequest(
            geometries=[
                {
                    "id": "zone_1",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    },
                }
            ],
            filters={"is_group": True},
            variables=["children_under_5"],
        )

        self.assertEqual(len(request.geometries), 1)
        self.assertEqual(request.geometries[0].id, "zone_1")
        self.assertEqual(request.filters, {"is_group": True})
        self.assertEqual(request.variables, ["children_under_5"])

    def test_batch_request_requires_geometries(self):
        """Test that BatchSpatialQueryRequest requires at least one geometry."""
        from pydantic import ValidationError

        from ..schemas.query import BatchSpatialQueryRequest

        with self.assertRaises(ValidationError):
            BatchSpatialQueryRequest(geometries=[])

    def test_batch_response_schema(self):
        """Test BatchSpatialQueryResponse structure with metadata."""
        from ..schemas.query import BatchSpatialQueryResponse

        response = BatchSpatialQueryResponse(
            results=[
                {
                    "id": "zone_1",
                    "total_count": 100,
                    "query_method": "coordinates",
                    "areas_matched": 2,
                    "statistics": {"total_households": 50},
                    "access_level": "aggregate",
                    "from_cache": False,
                    "computed_at": "2024-01-01T00:00:00Z",
                }
            ],
            summary={
                "total_count": 100,
                "geometries_queried": 1,
                "statistics": {"total_households": 50},
                "access_level": "aggregate",
                "from_cache": False,
                "computed_at": "2024-01-01T00:00:00Z",
            },
        )

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].id, "zone_1")
        self.assertEqual(response.results[0].access_level, "aggregate")
        self.assertFalse(response.results[0].from_cache)
        self.assertEqual(response.results[0].computed_at, "2024-01-01T00:00:00Z")
        self.assertEqual(response.summary.total_count, 100)
        self.assertEqual(response.summary.access_level, "aggregate")

    def test_geometry_item_schema(self):
        """Test GeometryItem schema."""
        from ..schemas.query import GeometryItem

        item = GeometryItem(
            id="flood_zone_1",
            geometry={
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]],
            },
        )

        self.assertEqual(item.id, "flood_zone_1")
        self.assertEqual(item.geometry["type"], "MultiPolygon")

    def test_batch_response_backward_compatibility(self):
        """Test that schemas work without metadata fields (backward compatibility)."""
        from ..schemas.query import BatchSpatialQueryResponse

        # Old-style response without metadata fields (should use defaults)
        response = BatchSpatialQueryResponse(
            results=[
                {
                    "id": "zone_1",
                    "total_count": 100,
                    "query_method": "coordinates",
                    "areas_matched": 2,
                    "statistics": {"total_households": 50},
                }
            ],
            summary={
                "total_count": 100,
                "geometries_queried": 1,
                "statistics": {"total_households": 50},
            },
        )

        # Metadata fields should have defaults
        self.assertIsNone(response.results[0].access_level)
        self.assertFalse(response.results[0].from_cache)
        self.assertIsNone(response.results[0].computed_at)
        self.assertIsNone(response.summary.access_level)
        self.assertFalse(response.summary.from_cache)
        self.assertIsNone(response.summary.computed_at)
