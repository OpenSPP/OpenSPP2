# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP integration tests for Geofence API endpoints.

Tests the actual HTTP endpoints including authentication enforcement,
status codes, content types, and parameter parsing.
"""

import json
import logging
import os
import unittest

from odoo.tests import tagged

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

_logger = logging.getLogger(__name__)

API_BASE = "/api/v2/spp"
GEOFENCE_BASE = f"{API_BASE}/gis/geofences"

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


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestGeofenceHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for Geofence API endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:all scope (covers geofence + read)
        cls.geofence_client = cls.create_api_client(
            cls,
            name="Geofence Write Client",
            scopes=[
                {"resource": "gis", "action": "all"},
            ],
        )
        cls.geofence_token = cls.generate_jwt_token(cls, cls.geofence_client)

        # Create API client with only gis:read scope (for list/get)
        cls.read_client = cls.create_api_client(
            cls,
            name="GIS Read Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.read_token = cls.generate_jwt_token(cls, cls.read_client)

        # Create API client without any gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

        # Create test geofence records directly via the model
        cls.geofence_a = cls.env["spp.gis.geofence"].create(
            {
                "name": "HTTP Test Geofence A",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
                "created_from": "api",
            }
        )
        cls.geofence_b = cls.env["spp.gis.geofence"].create(
            {
                "name": "HTTP Test Geofence B",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "service_area",
                "created_from": "api",
            }
        )

    def _geofence_headers(self):
        """Headers with valid gis:geofence + gis:read token."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.geofence_token}",
        }

    def _read_headers(self):
        """Headers with gis:read scope only."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.read_token}",
        }

    def _no_gis_headers(self):
        """Headers with token that lacks gis scopes."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    # ===================================================================
    # POST /geofences - Create geofence
    # ===================================================================

    def test_create_geofence_happy_path(self):
        """Test creating a geofence returns 201 with correct data."""
        payload = {
            "name": "HTTP Created Geofence",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "custom",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "HTTP Created Geofence")
        self.assertEqual(data["geofence_type"], "custom")
        self.assertTrue(data["active"])
        self.assertEqual(data["created_from"], "api")
        self.assertIn("id", data)
        # Check Location header
        self.assertIn("Location", response.headers)
        self.assertIn(str(data["id"]), response.headers["Location"])

    def test_create_geofence_with_description(self):
        """Test creating a geofence with optional description."""
        payload = {
            "name": "HTTP Described Geofence",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "service_area",
            "description": "A test description",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["description"], "A test description")
        self.assertEqual(data["geofence_type"], "service_area")

    def test_create_geofence_missing_scope_returns_403(self):
        """Test creating a geofence without gis:geofence scope returns 403."""
        payload = {
            "name": "Should Not Be Created",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "custom",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_create_geofence_no_scope_returns_403(self):
        """Test creating a geofence without any gis scope returns 403."""
        payload = {
            "name": "Should Not Be Created Either",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "custom",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_create_geofence_invalid_geometry_returns_422(self):
        """Test creating a geofence with invalid geometry returns 422."""
        payload = {
            "name": "Invalid Geometry Geofence",
            "geometry": {"type": "InvalidType", "coordinates": []},
            "geofence_type": "custom",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 422)

    def test_create_geofence_no_token_returns_401(self):
        """Test creating a geofence without token returns 401."""
        payload = {
            "name": "No Auth Geofence",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "custom",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)

    # ===================================================================
    # GET /geofences - List geofences
    # ===================================================================

    def test_list_geofences_happy_path(self):
        """Test listing geofences returns 200 with pagination."""
        response = self.url_open(GEOFENCE_BASE, headers=self._read_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("geofences", data)
        self.assertIn("total", data)
        self.assertIn("offset", data)
        self.assertIn("count", data)
        self.assertGreaterEqual(data["total"], 2)

    def test_list_geofences_with_type_filter(self):
        """Test listing geofences with geofence_type filter."""
        response = self.url_open(
            f"{GEOFENCE_BASE}?geofence_type=service_area",
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for geofence in data["geofences"]:
            self.assertEqual(geofence["geofence_type"], "service_area")

    def test_list_geofences_with_pagination(self):
        """Test listing geofences with pagination parameters."""
        response = self.url_open(
            f"{GEOFENCE_BASE}?_count=1&_offset=0",
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(data["count"], 1)
        self.assertEqual(data["offset"], 0)

    def test_list_geofences_missing_scope_returns_403(self):
        """Test listing geofences without gis:read scope returns 403."""
        response = self.url_open(GEOFENCE_BASE, headers=self._no_gis_headers())
        self.assertEqual(response.status_code, 403)

    def test_list_geofences_no_token_returns_401(self):
        """Test listing geofences without token returns 401."""
        response = self.url_open(
            GEOFENCE_BASE,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)

    def test_list_geofences_with_geofence_scope(self):
        """Test listing geofences with gis:geofence+gis:read scope succeeds."""
        response = self.url_open(GEOFENCE_BASE, headers=self._geofence_headers())
        self.assertEqual(response.status_code, 200)

    # ===================================================================
    # GET /geofences/{id} - Get geofence
    # ===================================================================

    def test_get_geofence_happy_path(self):
        """Test getting a single geofence returns 200 with GeoJSON Feature."""
        response = self.url_open(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "Feature")
        self.assertIn("geometry", data)
        self.assertIn("properties", data)
        self.assertEqual(data["properties"]["name"], "HTTP Test Geofence A")

    def test_get_geofence_not_found_returns_404(self):
        """Test getting a non-existent geofence returns 404."""
        response = self.url_open(
            f"{GEOFENCE_BASE}/99999999",
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_get_geofence_missing_scope_returns_403(self):
        """Test getting a geofence without gis:read scope returns 403."""
        response = self.url_open(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_get_geofence_no_token_returns_401(self):
        """Test getting a geofence without token returns 401."""
        response = self.url_open(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)

    # ===================================================================
    # DELETE /geofences/{id} - Delete (archive) geofence
    # ===================================================================

    def test_delete_geofence_happy_path(self):
        """Test deleting a geofence returns 204 and archives it."""
        # Create a geofence to delete
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "HTTP Geofence To Delete",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
                "created_from": "api",
            }
        )
        geofence_id = geofence.id

        response = self.url_delete(
            f"{GEOFENCE_BASE}/{geofence_id}",
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 204)

        # Verify the geofence is archived (active=False)
        geofence.invalidate_recordset()
        archived = self.env["spp.gis.geofence"].with_context(active_test=False).browse(geofence_id)
        self.assertFalse(archived.active)

    def test_delete_geofence_not_found_returns_404(self):
        """Test deleting a non-existent geofence returns 404."""
        response = self.url_delete(
            f"{GEOFENCE_BASE}/99999999",
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_geofence_missing_scope_returns_403(self):
        """Test deleting a geofence without gis:geofence scope returns 403."""
        response = self.url_delete(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers=self._read_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_geofence_no_scope_returns_403(self):
        """Test deleting a geofence without any gis scope returns 403."""
        response = self.url_delete(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_geofence_no_token_returns_401(self):
        """Test deleting a geofence without token returns 401."""
        response = self.url_delete(
            f"{GEOFENCE_BASE}/{self.geofence_a.id}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 401)

    def test_create_geofence_incident_code_not_found_returns_404(self):
        """Test creating geofence with nonexistent incident_code returns 404 (lines 75-81)."""
        payload = {
            "name": "Geofence With Bad Incident",
            "geometry": SAMPLE_POLYGON,
            "geofence_type": "hazard_zone",
            "incident_code": "NONEXISTENT_INCIDENT_CODE_XYZ",
        }
        response = self.url_open(
            GEOFENCE_BASE,
            data=json.dumps(payload),
            headers=self._geofence_headers(),
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("NONEXISTENT_INCIDENT_CODE_XYZ", data.get("detail", ""))
