# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the area fallback taken when the coordinate query fails.

``query_statistics`` catches failures from the coordinate-based query and
retries with the area-based query on the same cursor. A failed statement
aborts the PostgreSQL transaction, so the coordinate query has to run inside a
savepoint for the fallback to be reachable at all.
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


def _failing_coordinate_query(self, geometry_json, filters):
    """Stand-in for a coordinate query that dies inside PostgreSQL."""
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
