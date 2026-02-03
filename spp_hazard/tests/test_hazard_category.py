# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from psycopg2 import IntegrityError

from odoo.tests import mute_logger

from .common import HazardTestCase

_logger = logging.getLogger(__name__)


class TestHazardCategory(HazardTestCase):
    """Test cases for spp.hazard.category model."""

    def test_01_category_creation(self):
        """Test basic hazard category creation."""
        category = self.env["spp.hazard.category"].create(
            {
                "name": "Test Category",
                "code": "TEST_CAT",
            }
        )
        self.assertTrue(category)
        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.code, "TEST_CAT")
        self.assertTrue(category.active)

    def test_02_category_hierarchy(self):
        """Test parent-child relationship in categories."""
        # Check parent has child
        self.assertEqual(self.category_typhoon.parent_id, self.category_natural)
        self.assertIn(self.category_typhoon, self.category_natural.child_ids)

    def test_03_complete_name_computation(self):
        """Test complete name is computed correctly for hierarchical categories."""
        # Parent complete name should be just its name
        self.assertEqual(self.category_natural.complete_name, "Natural Disaster")

        # Child complete name should include parent
        expected = "Natural Disaster > Typhoon"
        self.assertEqual(self.category_typhoon.complete_name, expected)

    def test_04_category_code_unique_constraint(self):
        """Test that category codes must be unique."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hazard.category"].create(
                {
                    "name": "Duplicate Code Test",
                    "code": "NATURAL_TEST",  # Same code as category_natural
                }
            )

    def test_05_deactivate_category(self):
        """Test that categories can be deactivated."""
        category = self.env["spp.hazard.category"].create(
            {
                "name": "Temp Category",
                "code": "TEMP_CAT",
            }
        )
        self.assertTrue(category.active)

        category.write({"active": False})
        self.assertFalse(category.active)

    def test_06_incident_count(self):
        """Test incident count computation."""
        self.assertEqual(self.category_typhoon.incident_count, 0)

        # Create an incident for this category
        self.env["spp.hazard.incident"].create(
            {
                "name": "Test Typhoon",
                "code": "TEST-TYP-001",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )

        self.assertEqual(self.category_typhoon.incident_count, 1)

    def test_07_action_view_incidents(self):
        """Test the action to view incidents."""
        action = self.category_typhoon.action_view_incidents()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.hazard.incident")
        self.assertEqual(action["domain"], [("category_id", "=", self.category_typhoon.id)])
