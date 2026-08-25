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


class TestProximityAreaFallbackDoesNotPoisonTransaction(TransactionCase):
    """query_proximity's own area fallback must not leave the transaction aborted.

    Both legs of ``query_proximity`` run raw SQL. The area fallback
    (``_proximity_by_area``) has to run inside a savepoint just like the
    coordinate attempt: a genuine database error there still raises out of
    query_proximity, but the savepoint keeps the cursor usable for whatever
    runs next, instead of every later query failing with
    ``InFailedSqlTransaction``.
    """

    def test_non_finite_radius_does_not_abort_the_transaction(self):
        """A DB-level failure in the area fallback must not poison later queries."""
        from ..services.spatial_query_service import SpatialQueryService

        service = SpatialQueryService(self.env)

        # The coordinate attempt fails whether or not res.partner has a real
        # "coordinates" field: without one (this module's own test stack) it
        # raises a plain ValueError before touching the database, with one
        # (e.g. spp_registrant_gis installed) ST_Buffer rejects the
        # non-finite radius. Either way the coordinate leg's savepoint
        # recovers it, exactly as intended.
        #
        # query_proximity then falls back to _proximity_by_area, which
        # shares the same temp-table helper and is therefore handed the same
        # non-finite radius. ST_Buffer rejects a non-finite distance
        # argument at the database level ("distance must be a finite
        # value"), a genuine, deterministic PostGIS error, not a simulated
        # one: unlike an out-of-range or non-finite *coordinate*, which
        # PostGIS/GEOS only coerces or fails on inconsistently depending on
        # the exact computation involved, a non-finite *buffer distance* is
        # rejected by a straightforward argument check every time. Without a
        # savepoint around the fallback, this second failure would abort the
        # transaction.
        reference_points = [{"longitude": 28.0, "latitude": -2.0}]

        # Deliberately not self.assertRaises: TransactionCase overrides
        # assertRaises (see BaseCase._assertRaises in odoo/tests/common.py)
        # to wrap the block in its own savepoint and roll it back on the
        # expected exception. That would recover the transaction as a side
        # effect of the assertion itself, hiding exactly the bug this test
        # exists to catch. A plain try/except leaves the transaction exactly
        # as query_proximity left it, for the assertion below to see.
        raised = None
        with mute_logger("odoo.sql_db"):
            try:
                service.query_proximity(reference_points=reference_points, radius_km=float("nan"))
            except Exception as exc:
                raised = exc
        self.assertIsNotNone(raised, "query_proximity should raise when the area fallback hits a DB error")

        # An ordinary ORM query must still work; without the savepoint around
        # the area fallback, the aborted transaction raises
        # InFailedSqlTransaction here instead.
        self.env["res.partner"].search_count([])
