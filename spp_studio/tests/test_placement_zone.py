"""Tests for Studio placement zones."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPlacementZone(TransactionCase):
    """Test cases for spp.studio.placement.zone model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.PlacementZone = cls.env["spp.studio.placement.zone"]

    def test_create_placement_zone(self):
        """Test creating a placement zone."""
        zone = self.PlacementZone.create(
            {
                "name": "Test Zone",
                "code": "test_zone",
                "target_type": "individual",
                "tab_name": "Profile",
                "xpath_expression": "//group[@name='test']",
                "xpath_position": "inside",
            }
        )
        self.assertTrue(zone.exists())
        self.assertEqual(zone.code, "test_zone")
        self.assertEqual(zone.target_type, "individual")

    def test_zone_code_unique(self):
        """Test that zone codes must be unique."""
        self.PlacementZone.create(
            {
                "name": "Zone 1",
                "code": "unique_code",
                "target_type": "individual",
                "tab_name": "Profile",
                "xpath_expression": "//group[@name='test1']",
                "xpath_position": "inside",
            }
        )
        # Creating another zone with same code should fail
        with self.assertRaises(ValidationError):
            self.PlacementZone.create(
                {
                    "name": "Zone 2",
                    "code": "unique_code",
                    "target_type": "group",
                    "tab_name": "Profile",
                    "xpath_expression": "//group[@name='test2']",
                    "xpath_position": "inside",
                }
            )

    def test_zone_both_target_type(self):
        """Test zone with 'both' target type."""
        zone = self.PlacementZone.create(
            {
                "name": "Both Zone",
                "code": "both_zone",
                "target_type": "both",
                "tab_name": "Profile",
                "xpath_expression": "//group[@name='common']",
                "xpath_position": "inside",
            }
        )
        self.assertEqual(zone.target_type, "both")

    def test_zone_display_name(self):
        """Test zone display name format."""
        zone = self.PlacementZone.create(
            {
                "name": "My Zone",
                "code": "my_zone",
                "target_type": "individual",
                "tab_name": "Profile",
                "xpath_expression": "//test",
                "xpath_position": "inside",
            }
        )
        self.assertIn("My Zone", zone.display_name)

    def test_zone_xpath_positions(self):
        """Test all xpath position options."""
        positions = ["inside", "before", "after"]
        for idx, pos in enumerate(positions):
            zone = self.PlacementZone.create(
                {
                    "name": f"Zone {pos}",
                    "code": f"zone_{pos}_{idx}",
                    "target_type": "individual",
                    "tab_name": "Profile",
                    "xpath_expression": f"//group[@name='test_{pos}']",
                    "xpath_position": pos,
                }
            )
            self.assertEqual(zone.xpath_position, pos)
