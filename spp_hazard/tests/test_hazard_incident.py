# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import mute_logger

from .common import HazardTestCase

_logger = logging.getLogger(__name__)


class TestHazardIncident(HazardTestCase):
    """Test cases for spp.hazard.incident model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test incident
        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Test Typhoon Incident",
                "code": "TEST-INC-001",
                "category_id": cls.category_typhoon.id,
                "start_date": "2024-01-01",
                "severity_id": cls.severity_severe.id,
            }
        )

    def test_01_incident_creation(self):
        """Test basic incident creation."""
        self.assertTrue(self.incident)
        self.assertEqual(self.incident.name, "Test Typhoon Incident")
        self.assertEqual(self.incident.status, "active")  # default
        self.assertTrue(self.incident.is_ongoing)

    def test_02_incident_code_unique(self):
        """Test that incident codes must be unique."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hazard.incident"].create(
                {
                    "name": "Another Incident",
                    "code": "TEST-INC-001",  # Same code
                    "category_id": self.category_typhoon.id,
                    "start_date": "2024-01-15",
                }
            )

    def test_03_date_validation(self):
        """Test that end_date must be after start_date."""
        with self.assertRaises(ValidationError):
            self.env["spp.hazard.incident"].create(
                {
                    "name": "Invalid Dates Incident",
                    "code": "TEST-INC-002",
                    "category_id": self.category_typhoon.id,
                    "start_date": "2024-01-15",
                    "end_date": "2024-01-01",  # Before start_date
                }
            )

    def test_04_is_ongoing_computation(self):
        """Test is_ongoing computed field."""
        # Active incident with no end date should be ongoing
        self.assertTrue(self.incident.is_ongoing)

        # Set end date - should no longer be ongoing
        self.incident.write(
            {
                "end_date": "2024-01-15",
            }
        )
        self.assertFalse(self.incident.is_ongoing)

    def test_05_status_transitions(self):
        """Test status transition actions."""
        # Start in active status
        self.assertEqual(self.incident.status, "active")

        # Transition to recovery
        self.incident.action_set_recovery()
        self.assertEqual(self.incident.status, "recovery")

        # Back to active
        self.incident.action_set_active()
        self.assertEqual(self.incident.status, "active")

        # Close the incident
        self.incident.action_close()
        self.assertEqual(self.incident.status, "closed")
        self.assertTrue(self.incident.end_date)

    def test_06_area_linking(self):
        """Test linking areas to incident."""
        self.assertEqual(self.incident.area_count, 0)

        # Link area
        self.incident.write(
            {
                "area_ids": [(4, self.area.id)],
            }
        )
        self.assertEqual(self.incident.area_count, 1)
        self.assertIn(self.area, self.incident.area_ids)

    def test_07_incident_area_details(self):
        """Test incident area details with severity override."""
        incident_area = self.env["spp.hazard.incident.area"].create(
            {
                "incident_id": self.incident.id,
                "area_id": self.area.id,
                "severity_override_id": self.severity_extreme.id,
                "affected_population_estimate": 1000,
            }
        )
        self.assertTrue(incident_area)
        self.assertEqual(incident_area.severity_override_id, self.severity_extreme)
        self.assertEqual(incident_area.affected_population_estimate, 1000)

    def test_08_identify_potentially_affected(self):
        """Test identifying potentially affected registrants."""
        # Link area to incident
        self.incident.write(
            {
                "area_ids": [(4, self.area.id)],
            }
        )

        # Find affected registrants
        affected = self.incident.identify_potentially_affected_registrants()
        self.assertIn(self.registrant, affected)

    def test_09_impact_count(self):
        """Test impact count computation."""
        self.assertEqual(self.incident.impact_count, 0)

        # Create an impact
        self.env["spp.hazard.impact"].create(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )

        self.assertEqual(self.incident.impact_count, 1)
        self.assertEqual(self.incident.affected_registrant_count, 1)

    def test_10_action_view_impacts(self):
        """Test the action to view impacts."""
        action = self.incident.action_view_impacts()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hazard.impact")
        self.assertEqual(action["domain"], [("incident_id", "=", self.incident.id)])
