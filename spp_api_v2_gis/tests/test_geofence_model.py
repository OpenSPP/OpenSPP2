# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for geofence model extensions in spp_api_v2_gis.

Core geofence tests are in spp_gis/tests/test_geofence.py.
These tests cover only the fields and behavior added by spp_api_v2_gis and spp_hazard.
"""

import json
import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestGeofenceExtensions(TransactionCase):
    """Test geofence extensions from spp_api_v2_gis and spp_hazard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Sample polygon GeoJSON
        cls.sample_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 0.0],
                    [101.0, 0.0],
                    [101.0, 1.0],
                    [100.0, 1.0],
                    [100.0, 0.0],
                ]
            ],
        }

    def test_geofence_service_area_type(self):
        """Test that selection_add types from spp_api_v2_gis work."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Service Area Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "service_area",
            }
        )

        self.assertEqual(geofence.geofence_type, "service_area")

    def test_geofence_targeting_area_type(self):
        """Test that targeting_area type from spp_api_v2_gis works."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Targeting Area Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "targeting_area",
            }
        )

        self.assertEqual(geofence.geofence_type, "targeting_area")

    def test_geojson_properties_include_incident(self):
        """Test that incident fields appear in properties when spp_hazard adds them."""
        # incident_id should be available since spp_hazard is a dependency
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Incident Props Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
            }
        )

        feature = geofence.to_geojson()
        props = feature["properties"]

        # spp_api_v2_gis extends _get_geojson_properties with incident fields
        self.assertIn("incident_id", props)
        self.assertIn("incident_name", props)
        # No incident linked, so values should be None
        self.assertIsNone(props["incident_id"])
        self.assertIsNone(props["incident_name"])

    def test_geofence_type_label_service_area(self):
        """Test that service_area type label is correct."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Service Label Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "service_area",
            }
        )

        feature = geofence.to_geojson()
        props = feature["properties"]

        self.assertEqual(props["geofence_type"], "service_area")
        self.assertEqual(props["geofence_type_label"], "Service Area")
