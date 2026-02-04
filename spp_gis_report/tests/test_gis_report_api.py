# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo.tests import HttpCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestGISReportAPI(HttpCase):
    """Test the GeoJSON API controller endpoints using real HTTP requests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test area hierarchy
        cls.area_country = cls.env["spp.area"].create(
            {
                "draft_name": "API Test Country",
                "code": "API_TC",
                "area_level": 0,
            }
        )
        cls.area_region = cls.env["spp.area"].create(
            {
                "draft_name": "API Test Region",
                "code": "API_TC_R1",
                "parent_id": cls.area_country.id,
                "area_level": 1,
                "population": 100000,
            }
        )
        cls.area_district_1 = cls.env["spp.area"].create(
            {
                "draft_name": "API Test District 1",
                "code": "API_TC_R1_D1",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "population": 50000,
            }
        )
        cls.area_district_2 = cls.env["spp.area"].create(
            {
                "draft_name": "API Test District 2",
                "code": "API_TC_R1_D2",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "population": 50000,
            }
        )

        # Create test category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "API Test Category",
                "code": "api_test_cat",
            }
        )

        # Get model reference
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Create test report with data
        cls.test_report = cls.env["spp.gis.report"].create(
            {
                "name": "API Test Report",
                "code": "api_test_report",
                "category_id": cls.category.id,
                "source_model_id": cls.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Create test data for multiple areas
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.test_report.id,
                "area_id": cls.area_district_1.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.test_report.id,
                "area_id": cls.area_district_2.id,
                "raw_value": 200,
                "normalized_value": 200,
            }
        )
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.test_report.id,
                "area_id": cls.area_region.id,
                "raw_value": 300,
                "normalized_value": 300,
                "is_rollup": True,
            }
        )

        # Create report with disaggregation
        cls.report_disagg = cls.env["spp.gis.report"].create(
            {
                "name": "API Disaggregation Test",
                "code": "api_disagg_test",
                "category_id": cls.category.id,
                "source_model_id": cls.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "disaggregate_by_gender": True,
            }
        )
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.report_disagg.id,
                "area_id": cls.area_district_1.id,
                "raw_value": 100,
                "normalized_value": 100,
                "disaggregation": {"gender": {"male": 60, "female": 40}},
            }
        )

    def _get_json(self, url):
        """Make a GET request and parse JSON response.

        Args:
            url: The endpoint URL

        Returns:
            dict: Parsed JSON response
        """
        response = self.url_open(url)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 but got {response.status_code}: {response.text}",
        )
        return json.loads(response.text)

    def _get_json_with_status(self, url):
        """Make a GET request and return response with status.

        Args:
            url: The endpoint URL

        Returns:
            tuple: (status_code, parsed_json or None)
        """
        response = self.url_open(url)
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            data = None
        return response.status_code, data

    def _post_json(self, url):
        """Make a POST request and parse JSON response.

        Args:
            url: The endpoint URL

        Returns:
            dict: Parsed JSON response
        """
        # Use opener.post for explicit POST request
        full_url = self.base_url() + url
        response = self.opener.post(full_url, timeout=30)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 but got {response.status_code}: {response.text}",
        )
        return response.json()

    # =========================================================================
    # List Reports Tests
    # =========================================================================

    def test_01_list_reports_authenticated(self):
        """Test listing reports requires authentication and returns data."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport")

        self.assertIn("reports", result)
        self.assertIsInstance(result["reports"], list)

    def test_02_list_reports_structure(self):
        """Test list reports returns correct structure."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport")

        self.assertIn("reports", result)
        self.assertGreater(len(result["reports"]), 0)

        # Find our test report and verify structure
        test_report = next((r for r in result["reports"] if r["code"] == "api_test_report"), None)
        self.assertIsNotNone(test_report, "Test report should be in list")

        # Verify report structure
        self.assertIn("code", test_report)
        self.assertIn("name", test_report)
        self.assertIn("category", test_report)
        self.assertIn("last_refresh", test_report)
        self.assertIn("admin_levels_available", test_report)
        self.assertIn("has_disaggregation", test_report)

    def test_03_list_reports_includes_test_report(self):
        """Test list reports includes our test report with correct data."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport")

        # Find our test report
        report_codes = [r["code"] for r in result["reports"]]
        self.assertIn("api_test_report", report_codes)

        # Get our report data
        test_report_data = next(r for r in result["reports"] if r["code"] == "api_test_report")
        self.assertEqual(test_report_data["name"], "API Test Report")
        # Admin levels should include 1 (region) and 2 (districts)
        self.assertIn(2, test_report_data["admin_levels_available"])

    # =========================================================================
    # GeoJSON Endpoint Tests
    # =========================================================================

    def test_04_geojson_endpoint_basic(self):
        """Test basic GeoJSON endpoint returns FeatureCollection."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/geojson?include_geometry=false")

        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("features", result)
        self.assertIn("metadata", result)
        self.assertEqual(len(result["features"]), 3)  # 2 districts + 1 region

    def test_05_geojson_output_format(self):
        """Test GeoJSON output has correct feature structure."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/geojson?include_geometry=false")

        # Verify feature structure
        feature = result["features"][0]
        self.assertEqual(feature["type"], "Feature")
        self.assertIn("properties", feature)
        self.assertIn("geometry", feature)

        # Verify properties
        props = feature["properties"]
        self.assertIn("area_id", props)
        self.assertIn("area_code", props)
        self.assertIn("area_name", props)
        self.assertIn("area_level", props)
        self.assertIn("raw_value", props)
        self.assertIn("normalized_value", props)
        self.assertIn("display_value", props)
        self.assertIn("bucket", props)

        # Verify metadata
        metadata = result["metadata"]
        self.assertIn("report", metadata)
        self.assertIn("generated_at", metadata)
        self.assertIn("total_features", metadata)
        self.assertEqual(metadata["total_features"], 3)

    def test_06_geojson_admin_level_filter(self):
        """Test GeoJSON filtering by admin level."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/geojson?admin_level=2&include_geometry=false")

        # Should only have district data
        self.assertEqual(len(result["features"]), 2)
        for feature in result["features"]:
            self.assertEqual(feature["properties"]["area_level"], 2)

    def test_07_geojson_area_codes_filter(self):
        """Test GeoJSON filtering by area codes."""
        self.authenticate("admin", "admin")
        result = self._get_json(
            "/api/v2/GISReport/api_test_report/geojson?area_codes=API_TC_R1_D1&include_geometry=false"
        )

        # Should only have one feature
        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(
            result["features"][0]["properties"]["area_code"],
            "API_TC_R1_D1",
        )

    def test_08_geojson_area_codes_multiple(self):
        """Test GeoJSON filtering by multiple area codes."""
        self.authenticate("admin", "admin")
        result = self._get_json(
            "/api/v2/GISReport/api_test_report/geojson" "?area_codes=API_TC_R1_D1,API_TC_R1_D2&include_geometry=false"
        )

        # Should have both districts
        self.assertEqual(len(result["features"]), 2)

    def test_09_geojson_parent_area_filter(self):
        """Test GeoJSON filtering by parent area code."""
        self.authenticate("admin", "admin")
        result = self._get_json(
            "/api/v2/GISReport/api_test_report/geojson" "?parent_area_code=API_TC_R1&include_geometry=false"
        )

        # Should have 2 districts (children of region)
        self.assertEqual(len(result["features"]), 2)
        for feature in result["features"]:
            # All should be level 2 (districts)
            self.assertEqual(feature["properties"]["area_level"], 2)

    def test_10_geojson_simple_format(self):
        """Test GeoJSON simple format (features only, no metadata)."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/geojson?format=simple&include_geometry=false")

        # Should only have type and features
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("features", result)
        self.assertNotIn("metadata", result)

    def test_11_geojson_with_disaggregation(self):
        """Test GeoJSON includes disaggregation data when requested."""
        self.authenticate("admin", "admin")
        result = self._get_json(
            "/api/v2/GISReport/api_disagg_test/geojson" "?include_disaggregation=true&include_geometry=false"
        )

        # Verify disaggregation included
        feature = result["features"][0]
        self.assertIn("disaggregation", feature["properties"])
        self.assertIn("gender", feature["properties"]["disaggregation"])

    def test_12_geojson_report_not_found(self):
        """Test GeoJSON endpoint handles non-existent report."""
        self.authenticate("admin", "admin")
        status, result = self._get_json_with_status(
            "/api/v2/GISReport/nonexistent_report_code/geojson?include_geometry=false"
        )

        # Should return 404 error
        self.assertEqual(status, 404)
        self.assertIn("error", result)
        self.assertEqual(result["code"], "NOT_FOUND")

    # =========================================================================
    # Summary Endpoint Tests
    # =========================================================================

    def test_13_summary_endpoint_basic(self):
        """Test summary statistics endpoint."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/summary")

        # Verify structure
        self.assertIn("report_id", result)
        self.assertIn("area_count", result)
        self.assertIn("summary", result)
        self.assertIn("distribution", result)
        self.assertEqual(result["area_count"], 3)

    def test_14_summary_endpoint_statistics(self):
        """Test summary endpoint returns correct statistics."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/summary")

        # Verify statistics
        summary = result["summary"]
        self.assertEqual(summary["total_raw_value"], 600)  # 100 + 200 + 300
        self.assertEqual(summary["min_raw"], 100)
        self.assertEqual(summary["max_raw"], 300)

    def test_15_summary_endpoint_admin_level_filter(self):
        """Test summary endpoint with admin level filter."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/summary?admin_level=2")

        # Should only include districts
        self.assertEqual(result["area_count"], 2)
        self.assertEqual(result["summary"]["total_raw_value"], 300)  # 100 + 200

    def test_16_summary_endpoint_parent_area_filter(self):
        """Test summary endpoint with parent area code filter."""
        self.authenticate("admin", "admin")
        result = self._get_json("/api/v2/GISReport/api_test_report/summary?parent_area_code=API_TC_R1")

        # Should only include districts (children of region)
        self.assertEqual(result["area_count"], 2)

    def test_17_summary_endpoint_report_not_found(self):
        """Test summary endpoint handles non-existent report."""
        self.authenticate("admin", "admin")
        status, result = self._get_json_with_status("/api/v2/GISReport/nonexistent_report_code/summary")

        # Should return 404 error
        self.assertEqual(status, 404)
        self.assertIn("error", result)
        self.assertEqual(result["code"], "NOT_FOUND")

    # =========================================================================
    # Refresh Endpoint Tests
    # =========================================================================

    def test_18_refresh_endpoint_basic(self):
        """Test manual refresh endpoint."""
        self.authenticate("admin", "admin")
        result = self._post_json("/api/v2/GISReport/api_test_report/refresh")

        # Verify response
        self.assertIn("status", result)
        self.assertEqual(result["status"], "queued")
        self.assertIn("timestamp", result)
        self.assertIn("message", result)
        self.assertEqual(result["report_code"], "api_test_report")

    def test_19_refresh_endpoint_report_not_found(self):
        """Test refresh endpoint handles non-existent report."""
        self.authenticate("admin", "admin")
        full_url = self.base_url() + "/api/v2/GISReport/nonexistent_report_code/refresh"
        response = self.opener.post(full_url, timeout=30)

        # Should return 404 error
        self.assertEqual(response.status_code, 404)
        result = response.json()
        self.assertIn("error", result)
        self.assertEqual(result["code"], "NOT_FOUND")

    # =========================================================================
    # Authentication Tests
    # =========================================================================

    def test_20_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are denied."""
        # Don't authenticate - should get redirect or error
        response = self.url_open("/api/v2/GISReport", allow_redirects=False)

        # Unauthenticated requests to auth="user" endpoints get redirected to login
        # or return 303 (See Other) redirect
        self.assertIn(
            response.status_code,
            [303, 401, 403],
            f"Expected redirect or auth error but got {response.status_code}",
        )
