# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for geofence extensions in spp_hazard."""

import json
import logging

from odoo.tests import tagged

from .common import HazardTestCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHazardGeofence(HazardTestCase):
    """Test geofence extensions added by spp_hazard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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

        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Geofence Test Typhoon",
                "code": "GEO-TEST-INC-001",
                "category_id": cls.category_typhoon.id,
                "start_date": "2024-06-01",
                "severity_id": cls.severity_severe.id,
            }
        )

    def test_hazard_zone_geofence_type(self):
        """Test that hazard_zone type is available via selection_add."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Hazard Zone Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
            }
        )

        self.assertEqual(geofence.geofence_type, "hazard_zone")

    def test_geofence_with_incident(self):
        """Test linking a geofence to a hazard incident."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Incident Linked Geofence",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
                "incident_id": self.incident.id,
            }
        )

        self.assertEqual(geofence.incident_id, self.incident)
        self.assertEqual(geofence.incident_id.name, "Geofence Test Typhoon")
        self.assertEqual(geofence.incident_id.code, "GEO-TEST-INC-001")

    def test_geofence_incident_ondelete_set_null(self):
        """Test that deleting an incident sets geofence incident_id to null."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Temporary Incident",
                "code": "GEO-TEST-INC-DEL",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-06-15",
            }
        )

        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Ondelete Test Geofence",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
                "incident_id": incident.id,
            }
        )

        self.assertTrue(geofence.incident_id)

        incident.unlink()
        self.assertFalse(geofence.incident_id)

    def test_hazard_zone_type_label(self):
        """Test that hazard_zone type label is correct in GeoJSON properties."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Hazard Label Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
            }
        )

        props = geofence.to_geojson()["properties"]
        self.assertEqual(props["geofence_type"], "hazard_zone")
        self.assertEqual(props["geofence_type_label"], "Hazard Zone")

    def test_geofence_without_incident(self):
        """Test that geofence works fine without an incident linked."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "No Incident Geofence",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "hazard_zone",
            }
        )

        self.assertFalse(geofence.incident_id)
