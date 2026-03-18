# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import mute_logger

from .common import HazardTestCase


class TestHazardImpact(HazardTestCase):
    """Test cases for spp.hazard.impact model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test incident
        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Test Impact Incident",
                "code": "TEST-IMPACT-INC",
                "category_id": cls.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )

        # Create a test impact
        cls.impact = cls.env["spp.hazard.impact"].create(
            {
                "incident_id": cls.incident.id,
                "registrant_id": cls.registrant.id,
                "impact_type_id": cls.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )

    def test_01_impact_creation(self):
        """Test basic impact creation."""
        self.assertTrue(self.impact)
        self.assertEqual(self.impact.verification_status, "reported")  # default
        self.assertEqual(self.impact.damage_level, "moderate")

    def test_02_impact_date_validation(self):
        """Test that impact_date cannot be before incident start_date."""
        with self.assertRaises(ValidationError):
            self.env["spp.hazard.impact"].create(
                {
                    "incident_id": self.incident.id,
                    "registrant_id": self.registrant.id,
                    "impact_type_id": self.impact_type_property.id,
                    "damage_level": "severe",
                    "impact_date": "2023-12-01",  # Before incident start
                }
            )

    def test_03_duplicate_impact_constraint(self):
        """Test unique constraint on incident + registrant + type."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hazard.impact"].create(
                {
                    "incident_id": self.incident.id,
                    "registrant_id": self.registrant.id,
                    "impact_type_id": self.impact_type_displacement.id,  # Same type
                    "damage_level": "severe",
                    "impact_date": "2024-01-02",
                }
            )

    def test_04_different_impact_type_allowed(self):
        """Test that same registrant can have different impact types for same incident."""
        impact2 = self.env["spp.hazard.impact"].create(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_property.id,  # Different type
                "damage_level": "severe",
                "impact_date": "2024-01-02",
            }
        )
        self.assertTrue(impact2)

    def test_05_verification_workflow(self):
        """Test verification status transitions."""
        # Start as reported
        self.assertEqual(self.impact.verification_status, "reported")
        self.assertFalse(self.impact.verified_by_id)
        self.assertFalse(self.impact.verified_date)

        # Verify the impact
        self.impact.action_verify()
        self.assertEqual(self.impact.verification_status, "verified")
        self.assertTrue(self.impact.verified_by_id)
        self.assertTrue(self.impact.verified_date)

        # Dispute the impact
        self.impact.action_dispute()
        self.assertEqual(self.impact.verification_status, "disputed")

        # Reset to reported
        self.impact.action_reset_to_reported()
        self.assertEqual(self.impact.verification_status, "reported")
        self.assertFalse(self.impact.verified_by_id)
        self.assertFalse(self.impact.verified_date)

    def test_06_close_impact(self):
        """Test closing an impact record."""
        self.impact.action_close()
        self.assertEqual(self.impact.verification_status, "closed")

    def test_07_bulk_create_impacts(self):
        """Test bulk creation of impacts for registrants in an area."""
        # Create another registrant in the same area
        registrant2 = self.env["res.partner"].create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": self.area.id,
            }
        )

        # Create a new incident
        incident2 = self.env["spp.hazard.incident"].create(
            {
                "name": "Bulk Test Incident",
                "code": "BULK-INC-001",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-02-01",
            }
        )

        # Bulk create impacts
        created = self.env["spp.hazard.impact"].bulk_create_impacts(
            incident2,
            self.area,
            self.impact_type_displacement,
            "severe",
        )

        # Both registrants should have impacts
        self.assertEqual(len(created), 2)
        registrant_ids = created.mapped("registrant_id").ids
        self.assertIn(self.registrant.id, registrant_ids)
        self.assertIn(registrant2.id, registrant_ids)

    def test_08_bulk_create_skips_existing(self):
        """Test that bulk create skips registrants with existing impacts."""
        # Existing impact already created in setUpClass

        # Bulk create should skip existing
        created = self.env["spp.hazard.impact"].bulk_create_impacts(
            self.incident,
            self.area,
            self.impact_type_displacement,
            "severe",
        )

        # Should not create duplicate
        self.assertEqual(len(created), 0)

    def test_09_related_fields(self):
        """Test related fields are computed correctly."""
        self.assertEqual(self.impact.incident_name, self.incident.name)
        self.assertEqual(self.impact.incident_status, self.incident.status)
        self.assertEqual(self.impact.registrant_name, self.registrant.name)
        self.assertEqual(self.impact.impact_type_category, "physical")

    def test_10_onchange_incident_sets_date(self):
        """Test that onchange sets default impact_date from incident."""
        # Create new impact without date
        new_impact = self.env["spp.hazard.impact"].new(
            {
                "incident_id": self.incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_property.id,
                "damage_level": "minimal",
            }
        )
        new_impact._onchange_incident_id()
        self.assertEqual(new_impact.impact_date, self.incident.start_date)
