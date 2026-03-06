# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo.tests import TransactionCase


class TestRegistrantGIS(TransactionCase):
    """Test GIS coordinates on registrants."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]

    def test_coordinates_field_exists(self):
        """Test that coordinates field is available on res.partner."""
        # Create a test registrant
        registrant = self.partner_model.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
            }
        )

        # Verify coordinates field exists and can be written
        self.assertIn("coordinates", registrant._fields)

        # Test setting coordinates as GeoJSON
        test_coords = json.dumps({"type": "Point", "coordinates": [121.0, 14.0]})
        registrant.write({"coordinates": test_coords})

        # Verify coordinates can be read back
        self.assertTrue(registrant.coordinates)

    def test_coordinates_on_individual(self):
        """Test coordinates on individual registrant."""
        individual = self.partner_model.create(
            {
                "name": "DOE, John",
                "family_name": "Doe",
                "given_name": "John",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Set coordinates
        coords = json.dumps({"type": "Point", "coordinates": [120.5, 15.5]})
        individual.write({"coordinates": coords})

        # Verify
        self.assertTrue(individual.coordinates)

    def test_coordinates_on_group(self):
        """Test coordinates on group registrant."""
        group = self.partner_model.create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Set coordinates
        coords = json.dumps({"type": "Point", "coordinates": [122.0, 13.0]})
        group.write({"coordinates": coords})

        # Verify
        self.assertTrue(group.coordinates)

    def test_coordinates_empty_by_default(self):
        """Test that coordinates is empty by default."""
        registrant = self.partner_model.create(
            {
                "name": "New Registrant",
                "is_registrant": True,
            }
        )

        # Coordinates should be False/empty by default
        self.assertFalse(registrant.coordinates)
