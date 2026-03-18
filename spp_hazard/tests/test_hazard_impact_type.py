# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.tests import mute_logger

from .common import HazardTestCase


class TestHazardImpactType(HazardTestCase):
    """Test cases for spp.hazard.impact.type model."""

    def test_01_impact_type_creation(self):
        """Test basic impact type creation."""
        impact_type = self.env["spp.hazard.impact.type"].create(
            {
                "name": "Test Impact Type",
                "code": "TEST_IMPACT",
                "category": "economic",
            }
        )
        self.assertTrue(impact_type)
        self.assertEqual(impact_type.category, "economic")
        self.assertTrue(impact_type.active)

    def test_02_code_unique_constraint(self):
        """Test that impact type codes must be unique."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hazard.impact.type"].create(
                {
                    "name": "Duplicate Code",
                    "code": "DISPLACEMENT_TEST",  # Same as fixture
                    "category": "physical",
                }
            )

    def test_03_impact_count(self):
        """Test impact count computation."""
        self.assertEqual(self.impact_type_displacement.impact_count, 0)

        # Create incident and impact
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Count Test Incident",
                "code": "COUNT-INC",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )

        self.env["spp.hazard.impact"].create(
            {
                "incident_id": incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )

        self.assertEqual(self.impact_type_displacement.impact_count, 1)

    def test_04_deactivate_impact_type(self):
        """Test that impact types can be deactivated."""
        impact_type = self.env["spp.hazard.impact.type"].create(
            {
                "name": "Temp Impact Type",
                "code": "TEMP_IMPACT",
                "category": "social",
            }
        )
        self.assertTrue(impact_type.active)

        impact_type.write({"active": False})
        self.assertFalse(impact_type.active)

    def test_05_all_categories(self):
        """Test all impact type categories."""
        categories = ["physical", "economic", "health", "social"]
        for i, cat in enumerate(categories):
            impact_type = self.env["spp.hazard.impact.type"].create(
                {
                    "name": f"Category {cat}",
                    "code": f"CAT_{cat.upper()}_{i}",
                    "category": cat,
                }
            )
            self.assertEqual(impact_type.category, cat)

    def test_06_sequence_ordering(self):
        """Test that impact types can be ordered by sequence."""
        type1 = self.env["spp.hazard.impact.type"].create(
            {
                "name": "Type A",
                "code": "TYPE_A",
                "category": "physical",
                "sequence": 100,
            }
        )
        type2 = self.env["spp.hazard.impact.type"].create(
            {
                "name": "Type B",
                "code": "TYPE_B",
                "category": "physical",
                "sequence": 1,
            }
        )

        # Type B should come before Type A due to lower sequence
        types = self.env["spp.hazard.impact.type"].search(
            [
                ("code", "in", ["TYPE_A", "TYPE_B"]),
            ]
        )
        self.assertEqual(types[0], type2)  # Lower sequence first
        self.assertEqual(types[1], type1)  # Higher sequence second
