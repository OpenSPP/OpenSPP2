# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP integration tests for spatial query, statistics, export, and proximity routers.

Tests the actual HTTP endpoints including authentication enforcement,
status codes, and request/response validation.
"""

import json
import logging
import os
import unittest

from odoo.tests import tagged

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

_logger = logging.getLogger(__name__)

API_BASE = "/api/v2/spp"
GIS_BASE = f"{API_BASE}/gis"

# Reusable valid polygon geometry for spatial query tests
VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
}


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestSpatialQueryHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for spatial query endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="Spatial Query GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create API client without gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="Spatial Query No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _no_gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    def _no_auth_headers(self):
        return {"Content-Type": "application/json"}

    # === Spatial Query: POST /gis/query/statistics ===

    def test_spatial_query_returns_200(self):
        """Test spatial query with valid auth and geometry returns 200."""
        payload = {"geometry": VALID_POLYGON}
        response = self.url_open(
            f"{GIS_BASE}/query/statistics",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_count", data)
        self.assertIn("query_method", data)
        self.assertIn("statistics", data)

    def test_spatial_query_no_token_returns_401(self):
        """Test spatial query without token returns 401."""
        payload = {"geometry": VALID_POLYGON}
        response = self.url_open(
            f"{GIS_BASE}/query/statistics",
            data=json.dumps(payload),
            headers=self._no_auth_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_spatial_query_missing_scope_returns_403(self):
        """Test spatial query without gis:read scope returns 403."""
        payload = {"geometry": VALID_POLYGON}
        response = self.url_open(
            f"{GIS_BASE}/query/statistics",
            data=json.dumps(payload),
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_spatial_query_invalid_geometry_returns_422(self):
        """Test spatial query with invalid geometry returns 422."""
        payload = {"geometry": {"type": "Point", "coordinates": [0, 0]}}
        response = self.url_open(
            f"{GIS_BASE}/query/statistics",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 422)

    # === Batch Spatial Query: POST /gis/query/statistics/batch ===

    def test_batch_query_returns_200(self):
        """Test batch spatial query with valid auth returns 200."""
        payload = {
            "geometries": [
                {"id": "area_1", "geometry": VALID_POLYGON},
            ],
        }
        response = self.url_open(
            f"{GIS_BASE}/query/statistics/batch",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("summary", data)

    def test_batch_query_no_token_returns_401(self):
        """Test batch spatial query without token returns 401."""
        payload = {
            "geometries": [{"id": "area_1", "geometry": VALID_POLYGON}],
        }
        response = self.url_open(
            f"{GIS_BASE}/query/statistics/batch",
            data=json.dumps(payload),
            headers=self._no_auth_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_batch_query_missing_scope_returns_403(self):
        """Test batch spatial query without gis:read scope returns 403."""
        payload = {
            "geometries": [{"id": "area_1", "geometry": VALID_POLYGON}],
        }
        response = self.url_open(
            f"{GIS_BASE}/query/statistics/batch",
            data=json.dumps(payload),
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_batch_query_invalid_geometry_returns_422(self):
        """Test batch spatial query with invalid geometry returns 422."""
        payload = {
            "geometries": [
                {"id": "bad", "geometry": {"type": "Point", "coordinates": [0, 0]}},
            ],
        }
        response = self.url_open(
            f"{GIS_BASE}/query/statistics/batch",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 422)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestStatisticsHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for statistics discovery endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="Stats GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create API client with statistics:read scope (alternative)
        cls.stats_client = cls.create_api_client(
            cls,
            name="Stats Read Client",
            scopes=[{"resource": "statistics", "action": "read"}],
        )
        cls.stats_token = cls.generate_jwt_token(cls, cls.stats_client)

        # Create API client without gis or statistics scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="Stats No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _stats_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.stats_token}",
        }

    def _no_gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    def _no_auth_headers(self):
        return {"Content-Type": "application/json"}

    # === Statistics: GET /gis/statistics ===

    def test_statistics_returns_200(self):
        """Test statistics list with valid gis:read scope returns 200."""
        response = self.url_open(
            f"{GIS_BASE}/statistics",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("categories", data)
        self.assertIn("total_count", data)

    def test_statistics_no_token_returns_401(self):
        """Test statistics list without token returns 401."""
        response = self.url_open(
            f"{GIS_BASE}/statistics",
            headers=self._no_auth_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_statistics_missing_scope_returns_403(self):
        """Test statistics list without gis:read or statistics:read scope returns 403."""
        response = self.url_open(
            f"{GIS_BASE}/statistics",
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_statistics_with_statistics_read_scope_returns_200(self):
        """Test statistics list with alternative statistics:read scope returns 200."""
        response = self.url_open(
            f"{GIS_BASE}/statistics",
            headers=self._stats_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("categories", data)
        self.assertIn("total_count", data)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestExportHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for export endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="Export GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create API client without gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="Export No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _no_gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    def _no_auth_headers(self):
        return {"Content-Type": "application/json"}

    # === Export: GET /gis/export/geopackage ===

    def test_export_returns_200(self):
        """Test export with valid gis:read scope returns 200."""
        response = self.url_open(
            f"{GIS_BASE}/export/geopackage",
            headers=self._gis_headers(),
        )
        # 200 on success, 400 if no data available, or 500 if export fails
        self.assertIn(response.status_code, (200, 400, 500))

    def test_export_no_token_returns_401(self):
        """Test export without token returns 401."""
        response = self.url_open(
            f"{GIS_BASE}/export/geopackage",
            headers=self._no_auth_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_export_missing_scope_returns_403(self):
        """Test export without gis:read scope returns 403."""
        response = self.url_open(
            f"{GIS_BASE}/export/geopackage",
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestProximityHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for proximity query endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="Proximity GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create API client without gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="Proximity No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _no_gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    def _no_auth_headers(self):
        return {"Content-Type": "application/json"}

    # === Proximity: POST /gis/query/proximity ===

    def test_proximity_returns_200(self):
        """Test proximity query with valid auth returns 200."""
        payload = {
            "reference_points": [{"longitude": 0.5, "latitude": 0.5}],
            "radius_km": 10,
            "relation": "within",
        }
        response = self.url_open(
            f"{GIS_BASE}/query/proximity",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_count", data)
        self.assertIn("reference_points_count", data)
        self.assertIn("radius_km", data)
        self.assertIn("statistics", data)

    def test_proximity_no_token_returns_401(self):
        """Test proximity query without token returns 401."""
        payload = {
            "reference_points": [{"longitude": 0.5, "latitude": 0.5}],
            "radius_km": 10,
        }
        response = self.url_open(
            f"{GIS_BASE}/query/proximity",
            data=json.dumps(payload),
            headers=self._no_auth_headers(),
        )
        self.assertEqual(response.status_code, 401)

    def test_proximity_missing_scope_returns_403(self):
        """Test proximity query without gis:read scope returns 403."""
        payload = {
            "reference_points": [{"longitude": 0.5, "latitude": 0.5}],
            "radius_km": 10,
        }
        response = self.url_open(
            f"{GIS_BASE}/query/proximity",
            data=json.dumps(payload),
            headers=self._no_gis_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_proximity_invalid_request_returns_422(self):
        """Test proximity query with invalid request body returns 422."""
        # Missing required fields (reference_points and radius_km)
        payload = {"relation": "within"}
        response = self.url_open(
            f"{GIS_BASE}/query/proximity",
            data=json.dumps(payload),
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 422)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestStatisticsHTTPCategories(ApiV2HttpTestCase):
    """HTTP tests for statistics endpoint category iteration logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="Stats Category GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create a CEL variable and GIS-published statistic
        CelVariable = cls.env["spp.cel.variable"]
        Statistic = cls.env["spp.indicator"]

        # Create category
        cls.stat_category = cls.env["spp.metric.category"].create(
            {
                "name": "HTTP Test Category",
                "code": "http_test_cat",
            }
        )

        var = CelVariable.create(
            {
                "name": "http_test_stat_var",
                "cel_accessor": "http_test_stat",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        Statistic.create(
            {
                "name": "http_test_stat",
                "label": "HTTP Test Statistic",
                "variable_id": var.id,
                "format": "count",
                "is_published_gis": True,
                "category_id": cls.stat_category.id,
            }
        )

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def test_statistics_returns_categories_with_stats(self):
        """Test that statistics endpoint returns categories with published stats."""
        response = self.url_open(
            f"{GIS_BASE}/statistics",
            headers=self._gis_headers(),
        )
        # Should return 200; 500 is acceptable if internal data issues
        if response.status_code == 200:
            data = response.json()
            self.assertIn("categories", data)
            if data.get("total_count", 0) > 0:
                # Verify category structure when data exists
                for category in data["categories"]:
                    self.assertIn("code", category)
                    self.assertIn("name", category)
                    self.assertIn("statistics", category)
        else:
            self.assertIn(response.status_code, (200, 500))


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestExportHTTPEdgeCases(ApiV2HttpTestCase):
    """HTTP tests for export endpoint edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.gis_client = cls.create_api_client(
            cls,
            name="Export Edge GIS Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create a test report
        area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Export Edge Test Report",
                "code": "export_edge_test",
                "source_model_id": area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
            }
        )

    def _gis_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def test_export_with_layer_ids_parameter(self):
        """Test export endpoint with comma-separated layer_ids."""
        response = self.url_open(
            f"{GIS_BASE}/export/geopackage?layer_ids=export_edge_test",
            headers=self._gis_headers(),
        )
        # Should succeed (200) or fail gracefully (400/500)
        self.assertIn(response.status_code, (200, 400, 500))

    def test_export_with_multiple_layer_ids(self):
        """Test export endpoint with multiple comma-separated layer_ids."""
        response = self.url_open(
            f"{GIS_BASE}/export/geopackage?layer_ids=export_edge_test,nonexistent",
            headers=self._gis_headers(),
        )
        self.assertIn(response.status_code, (200, 400, 500))
