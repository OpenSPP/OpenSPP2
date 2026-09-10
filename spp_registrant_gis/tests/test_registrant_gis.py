# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo.exceptions import ValidationError
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

    # ── OP#1143 QA round 1: out-of-range values must be refused ──
    def test_latitude_out_of_range_is_refused(self):
        """QA round 1: an impossible latitude was accepted and stored.

        The map widget then threw a JavaScript error while projecting the point
        and kept throwing on every reopen, so the bad value could not be
        corrected. Reject it on write instead, where the user still has the
        form in front of them.
        """
        registrant = self.partner_model.create({"name": "Bad Latitude", "is_registrant": True})
        with self.assertRaises(ValidationError):
            registrant.write({"gis_latitude": 999.0, "gis_longitude": 120.0})

    def test_longitude_out_of_range_is_refused(self):
        registrant = self.partner_model.create({"name": "Bad Longitude", "is_registrant": True})
        with self.assertRaises(ValidationError):
            registrant.write({"gis_latitude": 10.0, "gis_longitude": 5000.0})

    def test_negative_out_of_range_is_refused(self):
        """The range is two-sided: -91 is as invalid as 91."""
        registrant = self.partner_model.create({"name": "Negative Bad", "is_registrant": True})
        with self.assertRaises(ValidationError):
            registrant.write({"gis_latitude": -91.0, "gis_longitude": 0.0})
        with self.assertRaises(ValidationError):
            registrant.write({"gis_latitude": 0.0, "gis_longitude": -181.0})

    def test_range_boundaries_are_accepted(self):
        """The poles and the antimeridian are legitimate coordinates."""
        registrant = self.partner_model.create({"name": "Boundary", "is_registrant": True})
        registrant.write({"gis_latitude": 90.0, "gis_longitude": 180.0})
        self.assertAlmostEqual(registrant.gis_latitude, 90.0, places=5)
        registrant.write({"gis_latitude": -90.0, "gis_longitude": -180.0})
        self.assertAlmostEqual(registrant.gis_longitude, -180.0, places=5)

    def test_out_of_range_point_from_import_is_refused(self):
        """Import writes `coordinates` directly, bypassing the typed inputs."""
        registrant = self.partner_model.create({"name": "Bad Import", "is_registrant": True})
        with self.assertRaises(ValidationError):
            registrant.write({"coordinates": json.dumps({"type": "Point", "coordinates": [200.0, 95.0]})})

    def test_a_refused_value_leaves_the_record_correctable(self):
        """The point of the fix: the bad value must not be persisted.

        QA could not recover because the invalid coordinate had been saved and
        crashed the widget on every reopen.
        """
        registrant = self.partner_model.create({"name": "Recoverable", "is_registrant": True})
        registrant.write({"gis_latitude": 8.5, "gis_longitude": 124.75})

        with self.assertRaises(ValidationError):
            registrant.write({"gis_latitude": 999.0})
        registrant.invalidate_recordset()

        # The good value survived, and a correction still goes through.
        self.assertAlmostEqual(registrant.gis_latitude, 8.5, places=5)
        registrant.write({"gis_latitude": 9.0})
        self.assertAlmostEqual(registrant.gis_latitude, 9.0, places=5)
