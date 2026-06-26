# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP integration tests for OGC API - Features write endpoints (Part 4):
scope enforcement, geofence creation, and the OPTIONS discovery handler."""

import json

from odoo.tests import tagged

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

API_BASE = "/api/v2/spp"
OGC_BASE = f"{API_BASE}/gis/ogc"

GEOFENCE_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]]],
    },
    "properties": {
        "name": "CRUD Test Zone",
        "geofence_type": "area_of_interest",
        "description": "created via OGC POST test",
    },
}


@tagged("post_install", "-at_install")
class TestOGCCrudHTTP(ApiV2HttpTestCase):
    """HTTP tests for OGC Part 4 write endpoints on the geofences collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.geofence_client = cls.create_api_client(
            cls,
            name="OGC Geofence Client",
            scopes=[
                {"resource": "gis", "action": "read"},
                {"resource": "gis", "action": "geofence"},
            ],
        )
        cls.geofence_token = cls.generate_jwt_token(cls, cls.geofence_client)

        cls.read_only_client = cls.create_api_client(
            cls,
            name="OGC Read-Only Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.read_only_token = cls.generate_jwt_token(cls, cls.read_only_client)

    def _headers(self, token):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    def test_options_geofences_items_advertises_write_methods(self):
        """OPTIONS on the geofences items endpoint advertises write methods."""
        response = self.opener.options(
            self.base_url() + f"{OGC_BASE}/collections/geofences/items",
            headers=self._headers(self.geofence_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers.get("Allow", ""))

    def test_post_geofence_without_scope_returns_403(self):
        """Creating a geofence without gis:geofence scope is forbidden."""
        response = self.url_open(
            f"{OGC_BASE}/collections/geofences/items",
            data=json.dumps(GEOFENCE_FEATURE),
            headers=self._headers(self.read_only_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_post_geofence_with_scope_returns_201(self):
        """A client with gis:geofence scope can create a geofence."""
        response = self.url_open(
            f"{OGC_BASE}/collections/geofences/items",
            data=json.dumps(GEOFENCE_FEATURE),
            headers=self._headers(self.geofence_token),
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["type"], "Feature")
        self.assertEqual(body["properties"]["name"], "CRUD Test Zone")

    def test_delete_geofence_without_scope_returns_403(self):
        """Deleting a geofence without gis:geofence scope is forbidden."""
        response = self.url_delete(
            f"{OGC_BASE}/collections/geofences/items/00000000-0000-0000-0000-000000000000",
            headers=self._headers(self.read_only_token),
        )
        self.assertEqual(response.status_code, 403)
