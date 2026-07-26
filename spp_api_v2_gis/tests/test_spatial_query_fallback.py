# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the area fallbacks taken when a coordinate query fails.

``query_statistics`` and ``query_proximity`` both catch failures from their
coordinate-based query and retry with the area-based query on the same cursor.
A failed statement aborts the PostgreSQL transaction, so the coordinate query
has to run inside a savepoint for either fallback to be reachable at all.
"""

import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

SERVICE_LOGGER = "odoo.addons.spp_api_v2_gis.services.spatial_query_service"

# Polygon covering roughly lon 27.9..28.1 / lat -2.1..-1.9 (East Africa).
QUERY_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[27.9, -2.1], [28.1, -2.1], [28.1, -1.9], [27.9, -1.9], [27.9, -2.1]]],
}


# Centre of QUERY_POLYGON, used as the proximity reference point.
REFERENCE_POINTS = [{"longitude": 28.0, "latitude": -2.0}]


def _failing_coordinate_query(self, geometry_json, filters):
    """Stand-in for a coordinate query that dies inside PostgreSQL."""
    self.env.cr.execute("SELECT id FROM spp_table_that_does_not_exist")


def _failing_proximity_query(self, reference_points, radius_meters, relation, filters):
    """Stand-in for a proximity query that dies inside PostgreSQL."""
    self.env.cr.execute("SELECT id FROM spp_table_that_does_not_exist")


class TestCoordinateQueryFallback(TransactionCase):
    """The failed coordinate attempt must not poison the area fallback."""

    @classmethod
    def setUpClass(cls):
        """Create an area covering the query polygon plus a registrant in it."""
        super().setUpClass()

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Fallback Test Area",
                "code": "FALLBACK-AREA-001",
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
                "name": "Fallback Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

    def test_area_fallback_runs_after_failed_coordinate_query(self):
        """A SQL error in the coordinate query degrades to the area query."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        with (
            patch.object(SpatialQueryService, "_query_by_coordinates", _failing_coordinate_query),
            mute_logger("odoo.sql_db"),
            self.assertLogs(SERVICE_LOGGER, level="WARNING") as captured,
        ):
            result = service.query_statistics(geometry=QUERY_POLYGON)

        self.assertEqual(result["query_method"], "area_fallback")
        self.assertIn(self.group.id, result["registrant_ids"])
        self.assertTrue(
            any("Coordinate-based query failed" in message for message in captured.output),
            f"expected a fallback warning, got {captured.output}",
        )

    def test_cursor_stays_usable_after_failed_coordinate_query(self):
        """The transaction is still usable once the fallback has completed."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        with (
            patch.object(SpatialQueryService, "_query_by_coordinates", _failing_coordinate_query),
            mute_logger("odoo.sql_db"),
            self.assertLogs(SERVICE_LOGGER, level="WARNING"),
        ):
            service.query_statistics(geometry=QUERY_POLYGON)

        self.env.cr.execute("SELECT id FROM res_partner WHERE id = %s", [self.group.id])
        self.assertEqual(self.env.cr.fetchall(), [(self.group.id,)])


class TestProximityQueryFallback(TransactionCase):
    """query_proximity has the same fallback, and needs the same savepoint."""

    @classmethod
    def setUpClass(cls):
        """Create an area covering the reference point plus a registrant in it."""
        super().setUpClass()

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Proximity Fallback Test Area",
                "code": "FALLBACK-AREA-002",
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
                "name": "Proximity Fallback Test Household",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area.id,
            }
        )

    def test_area_fallback_runs_after_failed_proximity_query(self):
        """A SQL error in the proximity query degrades to the area query."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        with (
            patch.object(SpatialQueryService, "_proximity_by_coordinates", _failing_proximity_query),
            mute_logger("odoo.sql_db"),
            self.assertLogs(SERVICE_LOGGER, level="WARNING") as captured,
        ):
            result = service.query_proximity(reference_points=REFERENCE_POINTS, radius_km=10)

        self.assertEqual(result["query_method"], "area_fallback")
        self.assertIn(self.group.id, result["registrant_ids"])
        self.assertTrue(
            any("Coordinate-based proximity query failed" in message for message in captured.output),
            f"expected a fallback warning, got {captured.output}",
        )

    def test_cursor_stays_usable_after_failed_proximity_query(self):
        """The transaction is still usable once the fallback has completed."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        with (
            patch.object(SpatialQueryService, "_proximity_by_coordinates", _failing_proximity_query),
            mute_logger("odoo.sql_db"),
            self.assertLogs(SERVICE_LOGGER, level="WARNING"),
        ):
            service.query_proximity(reference_points=REFERENCE_POINTS, radius_km=10)

        self.env.cr.execute("SELECT id FROM res_partner WHERE id = %s", [self.group.id])
        self.assertEqual(self.env.cr.fetchall(), [(self.group.id,)])
