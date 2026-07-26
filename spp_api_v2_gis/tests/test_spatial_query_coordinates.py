# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the coordinate-based branch of the spatial query service.

``res.partner.coordinates`` is added by ``spp_registrant_gis``, which is not a
dependency of ``spp_api_v2_gis``. These tests create the PostGIS column and
declare the field on the model for the duration of the test so the coordinate
branch can be exercised without adding a module dependency.
"""

import json
from contextlib import contextmanager
from types import MappingProxyType
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase

# Polygon covering roughly lon 27.9..28.1 / lat -2.1..-1.9 (East Africa).
QUERY_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[27.9, -2.1], [28.1, -2.1], [28.1, -1.9], [27.9, -1.9], [27.9, -2.1]]],
}


@contextmanager
def declared_coordinates_field(env):
    """Declare ``coordinates`` on res.partner as ``spp_registrant_gis`` would.

    ``_query_by_coordinates`` refuses to run when the field is absent, so the
    field has to be visible on the model while the query runs. ``_fields`` is a
    read-only mapping, so the whole mapping is swapped for a widened copy.
    """
    partner_cls = type(env["res.partner"])
    widened = MappingProxyType({**partner_cls._fields, "coordinates": fields.GeoPointField()})
    with patch.object(partner_cls, "_fields", widened):
        yield


class TestQueryByCoordinates(TransactionCase):
    """Coordinate query must bind its parameters in the order the SQL expects."""

    @classmethod
    def setUpClass(cls):
        """Add the coordinates column and create registrants inside/outside the polygon."""
        super().setUpClass()

        # Mirrors the geometry(Point, 4326) column created by GeoPointField.
        cls.env.cr.execute("ALTER TABLE res_partner ADD COLUMN coordinates geometry(Point, 4326)")

        cls.group_inside = cls.env["res.partner"].create(
            {
                "name": "Coordinates Household Inside",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.individual_inside = cls.env["res.partner"].create(
            {
                "name": "Coordinates Individual Inside",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.group_outside = cls.env["res.partner"].create(
            {
                "name": "Coordinates Household Outside",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls._set_coordinates(cls.group_inside, 28.0, -2.0)
        cls._set_coordinates(cls.individual_inside, 28.01, -2.01)
        cls._set_coordinates(cls.group_outside, 32.0, -5.0)

    @classmethod
    def _set_coordinates(cls, partner, longitude, latitude):
        """Write a point into the raw coordinates column."""
        cls.env.cr.execute(
            "UPDATE res_partner SET coordinates = ST_SetSRID(ST_MakePoint(%s, %s), 4326) WHERE id = %s",
            [longitude, latitude, partner.id],
        )

    def _get_service(self):
        """Create a SpatialQueryService instance."""
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)

    def test_query_without_filters(self):
        """Without filters, every registrant inside the polygon is returned."""
        service = self._get_service()

        with declared_coordinates_field(self.env):
            result = service._query_by_coordinates(json.dumps(QUERY_POLYGON), {})

        self.assertEqual(result["query_method"], "coordinates")
        self.assertIn(self.group_inside.id, result["registrant_ids"])
        self.assertIn(self.individual_inside.id, result["registrant_ids"])
        self.assertNotIn(self.group_outside.id, result["registrant_ids"])

    def test_is_group_true_filter(self):
        """The is_group filter must be bound to p.is_group, not to the geometry."""
        service = self._get_service()

        with declared_coordinates_field(self.env):
            result = service._query_by_coordinates(json.dumps(QUERY_POLYGON), {"is_group": True})

        self.assertEqual(result["query_method"], "coordinates")
        self.assertIn(self.group_inside.id, result["registrant_ids"])
        self.assertNotIn(self.individual_inside.id, result["registrant_ids"])
        self.assertNotIn(self.group_outside.id, result["registrant_ids"])

    def test_is_group_false_filter(self):
        """is_group=False returns individuals inside the polygon only."""
        service = self._get_service()

        with declared_coordinates_field(self.env):
            result = service._query_by_coordinates(json.dumps(QUERY_POLYGON), {"is_group": False})

        self.assertEqual(result["query_method"], "coordinates")
        self.assertIn(self.individual_inside.id, result["registrant_ids"])
        self.assertNotIn(self.group_inside.id, result["registrant_ids"])
        self.assertNotIn(self.group_outside.id, result["registrant_ids"])

    def test_is_group_filter_combined_with_disabled_filter(self):
        """The disabled filter adds no placeholder and must not shift the params."""
        service = self._get_service()

        with declared_coordinates_field(self.env):
            result = service._query_by_coordinates(
                json.dumps(QUERY_POLYGON),
                {"is_group": True, "disabled": False},
            )

        self.assertEqual(result["query_method"], "coordinates")
        self.assertIn(self.group_inside.id, result["registrant_ids"])
        self.assertNotIn(self.individual_inside.id, result["registrant_ids"])
        self.assertNotIn(self.group_outside.id, result["registrant_ids"])
