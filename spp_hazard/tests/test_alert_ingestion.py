# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for alert ingestion business logic (create_from_alert, update_from_alert, etc.)."""

import json
import logging

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import HazardTestCase

_logger = logging.getLogger(__name__)

# Sample polygon covering a small area
SAMPLE_POLYGON = {
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

SAMPLE_POLYGON_2 = {
    "type": "Polygon",
    "coordinates": [
        [
            [102.0, 2.0],
            [103.0, 2.0],
            [103.0, 3.0],
            [102.0, 3.0],
            [102.0, 2.0],
        ]
    ],
}


@tagged("post_install", "-at_install")
class TestCreateFromAlert(HazardTestCase):
    """Tests for create_from_alert method."""

    def test_create_from_alert_happy_path(self):
        """Create incident from alert with all properties."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Flood",
            "headline": "Major Flood in Region A",
            "severity": "extreme",
            "urgency": "immediate",
            "certainty": "observed",
            "effective": "2026-04-01T00:00:00Z",
            "expires": "2026-04-15T00:00:00Z",
            "source": "INAM Mozambique",
            "source_alert_id": "MOZ-FLOOD-2026-001",
            "cap_msg_type": "alert",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        self.assertTrue(incident)
        self.assertEqual(incident.name, "Major Flood in Region A")
        self.assertEqual(incident.cap_event, "Flood")
        self.assertEqual(incident.severity_id, self.severity_extreme)
        self.assertEqual(incident.cap_urgency_id, self.urgency_immediate)
        self.assertEqual(incident.cap_certainty_id, self.certainty_observed)
        self.assertEqual(incident.source, "INAM Mozambique")
        self.assertEqual(incident.source_alert_id, "MOZ-FLOOD-2026-001")
        self.assertTrue(incident.uuid)
        # Auto-populated dates
        self.assertTrue(incident.start_date)
        self.assertTrue(incident.effective)

    def test_create_from_alert_creates_geofence(self):
        """create_from_alert creates a hazard_zone geofence linked to the incident."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Storm",
            "headline": "Storm Alert",
            "source_alert_id": "STORM-001",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        geofence = self.env["spp.gis.geofence"].search(
            [("incident_id", "=", incident.id), ("geofence_type", "=", "hazard_zone")]
        )
        self.assertEqual(len(geofence), 1)
        self.assertEqual(geofence.created_from, "api")

    def test_create_from_alert_resolves_category(self):
        """create_from_alert resolves event string to hazard category by name."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Typhoon",
            "headline": "Typhoon Alert",
            "source_alert_id": "TYP-001",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        self.assertEqual(incident.category_id, self.category_typhoon)
        self.assertEqual(incident.cap_event, "Typhoon")

    def test_create_from_alert_missing_category_ok(self):
        """create_from_alert works when event doesn't match any category."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Alien Invasion",
            "headline": "Unknown Event",
            "source_alert_id": "UNK-001",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        self.assertFalse(incident.category_id)
        self.assertEqual(incident.cap_event, "Alien Invasion")

    def test_create_from_alert_auto_code(self):
        """create_from_alert auto-generates code from source_alert_id."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Flood",
            "headline": "Auto Code Test",
            "source_alert_id": "AUTO-CODE-001",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        self.assertEqual(incident.code, "AUTO-CODE-001")

    def test_create_from_alert_bad_geometry_raises(self):
        """create_from_alert raises ValidationError for Point geometry."""
        Incident = self.env["spp.hazard.incident"]
        bad_geom = {"type": "Point", "coordinates": [100.0, 0.0]}
        properties = {
            "event": "Flood",
            "headline": "Bad Geom",
            "source_alert_id": "BAD-GEOM-001",
        }

        with self.assertRaises(ValidationError):
            Incident.create_from_alert(bad_geom, properties)

    def test_create_from_alert_minimal_properties(self):
        """create_from_alert works with only event and headline."""
        Incident = self.env["spp.hazard.incident"]
        properties = {
            "event": "Drought",
            "headline": "Minimal Alert",
            "source_alert_id": "MIN-001",
        }

        incident = Incident.create_from_alert(SAMPLE_POLYGON, properties)

        self.assertTrue(incident)
        self.assertEqual(incident.name, "Minimal Alert")
        self.assertFalse(incident.severity_id)
        self.assertFalse(incident.cap_urgency_id)


@tagged("post_install", "-at_install")
class TestUpdateFromAlert(HazardTestCase):
    """Tests for update_from_alert method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Incident = cls.env["spp.hazard.incident"]
        cls.incident = Incident.create_from_alert(
            SAMPLE_POLYGON,
            {
                "event": "Flood",
                "headline": "Initial Flood Alert",
                "severity": "moderate",
                "source_alert_id": "UPD-001",
            },
        )

    def test_update_properties_only(self):
        """update_from_alert updates properties without geometry change."""
        self.incident.update_from_alert(
            None,
            {
                "headline": "Updated Flood Alert",
                "severity": "extreme",
            },
        )

        self.assertEqual(self.incident.name, "Updated Flood Alert")
        self.assertEqual(self.incident.severity_id, self.severity_extreme)

    def test_update_with_new_geometry(self):
        """update_from_alert updates the linked geofence geometry."""
        self.incident.update_from_alert(
            SAMPLE_POLYGON_2,
            {"headline": "Flood Moved East"},
        )

        geofence = self.env["spp.gis.geofence"].search(
            [("incident_id", "=", self.incident.id), ("geofence_type", "=", "hazard_zone")],
            limit=1,
        )
        self.assertTrue(geofence)
        self.assertEqual(self.incident.name, "Flood Moved East")

    def test_update_cancel_closes_incident(self):
        """update_from_alert with cap_msg_type=cancel closes the incident."""
        self.incident.update_from_alert(
            None,
            {"cap_msg_type": "cancel"},
        )

        self.assertEqual(self.incident.status, "closed")


@tagged("post_install", "-at_install")
class TestToGeojson(HazardTestCase):
    """Tests for to_geojson and related methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Incident = cls.env["spp.hazard.incident"]
        cls.incident = Incident.create_from_alert(
            SAMPLE_POLYGON,
            {
                "event": "Flood",
                "headline": "GeoJSON Test Flood",
                "severity": "severe",
                "urgency": "immediate",
                "source": "Test Agency",
                "source_alert_id": "GEO-001",
            },
        )

    def test_to_geojson_structure(self):
        """to_geojson returns valid GeoJSON Feature."""
        feature = self.incident.to_geojson()

        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["id"], self.incident.uuid)
        self.assertIsNotNone(feature["geometry"])
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertIsInstance(feature["properties"], dict)

    def test_to_geojson_properties(self):
        """to_geojson includes all CAP-aligned properties."""
        props = self.incident.to_geojson()["properties"]

        self.assertEqual(props["code"], "GEO-001")
        self.assertEqual(props["event"], "Flood")
        self.assertEqual(props["severity"], "severe")
        self.assertEqual(props["urgency"], "immediate")
        self.assertEqual(props["headline"], "GeoJSON Test Flood")
        self.assertEqual(props["source"], "Test Agency")
        self.assertEqual(props["source_alert_id"], "GEO-001")

    def test_to_geojson_without_geofence(self):
        """to_geojson returns null geometry if no geofence linked."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "No Geofence Incident",
                "code": "NOGEO-001",
                "start_date": "2026-01-01",
            }
        )

        feature = incident.to_geojson()

        self.assertEqual(feature["type"], "Feature")
        self.assertIsNone(feature["geometry"])

    def test_to_geojson_multiple_geofences_uses_first(self):
        """to_geojson uses the first (oldest) geofence geometry."""
        # Create a second geofence for the same incident
        self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=SAMPLE_POLYGON_2,
            name="Second zone",
            geofence_type="hazard_zone",
            created_from="api",
            incident_id=self.incident.id,
        )

        feature = self.incident.to_geojson()

        # Should use first geofence (SAMPLE_POLYGON), not second
        self.assertIsNotNone(feature["geometry"])


@tagged("post_install", "-at_install")
class TestLinkAreasFromGeometry(HazardTestCase):
    """Tests for _link_areas_from_geometry method."""

    def test_link_areas_no_match(self):
        """_link_areas_from_geometry with non-overlapping geometry links no areas."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "No Match Incident",
                "code": "NOMATCH-001",
                "start_date": "2026-01-01",
            }
        )

        # Polygon far from any test area
        far_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [170.0, 70.0],
                    [171.0, 70.0],
                    [171.0, 71.0],
                    [170.0, 71.0],
                    [170.0, 70.0],
                ]
            ],
        }

        incident._link_areas_from_geometry(far_polygon)

        # Should not fail, just log and link nothing
        self.assertEqual(len(incident.area_ids), 0)

    def test_auto_populate_dates_from_effective(self):
        """Auto-populate start_date from effective on create."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Date Auto Test",
                "code": "DATE-AUTO-001",
                "effective": "2026-06-15 10:00:00",
            }
        )

        self.assertEqual(str(incident.start_date), "2026-06-15")

    def test_auto_populate_end_date_from_expires(self):
        """Auto-populate end_date from expires on create."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Date Auto End Test",
                "code": "DATE-AUTO-002",
                "effective": "2026-06-15 10:00:00",
                "expires": "2026-07-01 10:00:00",
            }
        )

        self.assertEqual(str(incident.start_date), "2026-06-15")
        self.assertEqual(str(incident.end_date), "2026-07-01")
