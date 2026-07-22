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

    # ── OP#1143: visible latitude/longitude inputs synced with coordinates ──
    def test_lat_long_computed_from_coordinates(self):
        """Setting coordinates populates the latitude/longitude inputs."""
        registrant = self.partner_model.create({"name": "LatLong From Point", "is_registrant": True})
        registrant.write({"coordinates": json.dumps({"type": "Point", "coordinates": [121.5, 14.25]})})
        self.assertAlmostEqual(registrant.gis_longitude, 121.5, places=5)
        self.assertAlmostEqual(registrant.gis_latitude, 14.25, places=5)

    def test_coordinates_built_from_lat_long(self):
        """Typing latitude/longitude rebuilds the coordinates point."""
        group = self.partner_model.create({"name": "LatLong Group", "is_registrant": True, "is_group": True})
        group.write({"gis_latitude": 8.5, "gis_longitude": 124.75})
        self.assertTrue(group.coordinates)
        self.assertAlmostEqual(group.coordinates.x, 124.75, places=5)  # x = longitude
        self.assertAlmostEqual(group.coordinates.y, 8.5, places=5)  # y = latitude

    def test_lat_long_empty_when_no_coordinates(self):
        """With no point set, the latitude/longitude inputs read as 0."""
        registrant = self.partner_model.create({"name": "No Coords", "is_registrant": True})
        self.assertEqual(registrant.gis_latitude, 0.0)
        self.assertEqual(registrant.gis_longitude, 0.0)
