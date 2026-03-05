# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""HTTP integration tests for OGC API - Features endpoints.

Tests the actual HTTP endpoints including authentication enforcement,
status codes, content types, and parameter parsing.
"""

import logging
import os
import unittest
from datetime import datetime, timedelta

from odoo.tests import tagged

from odoo.addons.spp_api_v2.tests.common import ApiV2HttpTestCase

_logger = logging.getLogger(__name__)

API_BASE = "/api/v2/spp"
OGC_BASE = f"{API_BASE}/gis/ogc"


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestOGCHTTP(ApiV2HttpTestCase):
    """HTTP integration tests for OGC API - Features endpoints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create GIS-specific test data
        cls.color_scheme = cls.env["spp.gis.color.scheme"].create(
            {
                "name": "HTTP Test Scheme",
                "code": "http_test_scheme",
                "scheme_type": "sequential",
                "colors": '["#440154", "#21918c", "#fde725"]',
                "default_steps": 3,
            }
        )

        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "HTTP Test Category",
                "code": "http_test_category",
                "sequence": 10,
            }
        )

        area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "HTTP Test Report",
                "code": "http_test_report",
                "description": "Report for HTTP integration tests",
                "category_id": cls.category.id,
                "source_model_id": area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": cls.color_scheme.id,
                "threshold_mode": "manual",
                "last_refresh": datetime.now() - timedelta(hours=1),
                "sequence": 10,
            }
        )

        # Create thresholds for QML generation
        cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 10,
                "min_value": 0,
                "max_value": 50,
                "color": "#440154",
                "label": "Low",
            }
        )
        cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 20,
                "min_value": 50,
                "max_value": None,
                "color": "#fde725",
                "label": "High",
            }
        )

        # Create area types and areas at multiple levels for per-level tests
        cls.area_type_country = cls.env["spp.area.type"].create({"name": "HTTP Country"})
        cls.area_type_region = cls.env["spp.area.type"].create({"name": "HTTP Region"})

        cls.http_area_country = cls.env["spp.area"].create(
            {
                "draft_name": "HTTP Test Country",
                "code": "http_test_country",
                "area_type_id": cls.area_type_country.id,
            }
        )
        cls.http_area_region = cls.env["spp.area"].create(
            {
                "draft_name": "HTTP Test Region",
                "code": "http_test_region",
                "parent_id": cls.http_area_country.id,
                "area_type_id": cls.area_type_region.id,
            }
        )

        # Create report data at both levels
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.report.id,
                "area_id": cls.http_area_country.id,
                "area_code": cls.http_area_country.code,
                "area_name": cls.http_area_country.draft_name,
                "area_level": cls.http_area_country.area_level,
                "raw_value": 1000.0,
                "normalized_value": 1.0,
                "display_value": "1000",
                "record_count": 1000,
            }
        )
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.report.id,
                "area_id": cls.http_area_region.id,
                "area_code": cls.http_area_region.code,
                "area_name": cls.http_area_region.draft_name,
                "area_level": cls.http_area_region.area_level,
                "raw_value": 500.0,
                "normalized_value": 0.5,
                "display_value": "500",
                "record_count": 500,
            }
        )

        # Create API client with gis:read scope
        cls.gis_client = cls.create_api_client(
            cls,
            name="GIS Test Client",
            scopes=[{"resource": "gis", "action": "read"}],
        )
        cls.gis_token = cls.generate_jwt_token(cls, cls.gis_client)

        # Create API client without gis scope
        cls.no_gis_client = cls.create_api_client(
            cls,
            name="No GIS Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        cls.no_gis_token = cls.generate_jwt_token(cls, cls.no_gis_client)

    def _gis_headers(self):
        """Headers with valid GIS token."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.gis_token}",
        }

    def _no_gis_headers(self):
        """Headers with token that lacks gis:read scope."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.no_gis_token}",
        }

    # === Auth enforcement ===

    def test_landing_page_no_token_returns_401(self):
        """Test landing page without token returns 401."""
        response = self.url_open(OGC_BASE, headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 401)

    def test_landing_page_no_gis_scope_returns_403(self):
        """Test landing page without gis:read scope returns 403."""
        response = self.url_open(OGC_BASE, headers=self._no_gis_headers())
        self.assertEqual(response.status_code, 403)

    # === Landing page ===

    def test_landing_page_returns_200(self):
        """Test landing page returns 200 with valid auth."""
        response = self.url_open(OGC_BASE, headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)

    def test_landing_page_has_links(self):
        """Test landing page response contains navigation links."""
        response = self.url_open(OGC_BASE, headers=self._gis_headers())
        data = response.json()
        self.assertIn("links", data)
        link_rels = [link["rel"] for link in data["links"]]
        self.assertIn("self", link_rels)
        self.assertIn("conformance", link_rels)
        self.assertIn("data", link_rels)

    # === Conformance ===

    def test_conformance_returns_200(self):
        """Test conformance endpoint returns 200."""
        response = self.url_open(f"{OGC_BASE}/conformance", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conformsTo", data)

    # === Collections ===

    def test_collections_returns_200_with_reports(self):
        """Test collections endpoint returns 200 and includes test report with _admN suffix."""
        response = self.url_open(f"{OGC_BASE}/collections", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("collections", data)
        collection_ids = [c["id"] for c in data["collections"]]
        # Report should appear with _admN suffixes (has data at multiple levels)
        report_collections = [cid for cid in collection_ids if cid.startswith("http_test_report")]
        self.assertGreater(len(report_collections), 0, "Report should appear in collections")

    def test_collection_not_found_returns_404(self):
        """Test non-existent collection returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/collections/nonexistent_collection",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    # === Items ===

    def test_items_returns_geojson_content_type(self):
        """Test items endpoint returns application/geo+json content type."""
        # Use bare code (backward compat defaults to base level)
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report/items",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/geo+json", response.headers.get("content-type", ""))

    def test_items_invalid_bbox_returns_400(self):
        """Test items with invalid bbox returns 400."""
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report/items?bbox=invalid",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_items_not_found_returns_404(self):
        """Test items for non-existent collection returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/collections/nonexistent/items",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    # === Single feature ===

    def test_feature_not_found_returns_404(self):
        """Test non-existent feature returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report/items/99999999",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    # === QML ===

    def test_qml_returns_xml_content_type(self):
        """Test QML endpoint returns text/xml content type."""
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/xml", response.headers.get("content-type", ""))

    def test_qml_for_nonexistent_data_layer_returns_404(self):
        """Test QML for nonexistent data layer returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/collections/layer_999/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_qml_for_report_driven_data_layer_returns_200(self):
        """Test QML for report-driven data layer returns 200 with XML."""
        # Create a report-driven data layer linked to the test report
        geo_field = self.env["ir.model.fields"].search(
            [("model", "=", "spp.area"), ("name", "=", "polygon")],
            limit=1,
        )
        if not geo_field:
            self.skipTest("No geo field available for data layer creation")
        report_layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "HTTP Report Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geo_field_id": geo_field.id,
                "geo_repr": "choropleth",
                "sequence": 99,
            }
        )
        response = self.url_open(
            f"{OGC_BASE}/collections/layer_{report_layer.id}/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/xml", response.headers.get("content-type", ""))

    def test_qml_for_model_driven_data_layer_returns_404(self):
        """Test QML for model-driven data layer returns 404."""
        geo_field = self.env["ir.model.fields"].search(
            [("model", "=", "spp.area"), ("name", "=", "polygon")],
            limit=1,
        )
        if not geo_field:
            self.skipTest("No geo field available for model-driven layer")

        model_layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "HTTP Model Layer",
                "source_type": "model",
                "model_name": "spp.area",
                "geo_field_id": geo_field.id,
                "geo_repr": "basic",
                "sequence": 98,
            }
        )
        response = self.url_open(
            f"{OGC_BASE}/collections/layer_{model_layer.id}/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_qml_for_invalid_layer_id_returns_404(self):
        """Test QML for layer with invalid ID format returns 404."""
        response = self.url_open(
            f"{OGC_BASE}/collections/layer_abc/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 404)

    # === Admin Level Split Tests ===

    def test_items_with_adm_suffix_returns_200(self):
        """Test items endpoint with _admN suffix returns 200."""
        level = self.http_area_country.area_level
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report_adm{level}/items",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/geo+json", response.headers.get("content-type", ""))

    def test_qml_with_adm_suffix_returns_200(self):
        """Test QML endpoint with _admN suffix returns 200."""
        level = self.http_area_country.area_level
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report_adm{level}/qml",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/xml", response.headers.get("content-type", ""))

    def test_bare_report_code_still_works(self):
        """Test bare report code still works for backward compatibility."""
        response = self.url_open(
            f"{OGC_BASE}/collections/http_test_report/items",
            headers=self._gis_headers(),
        )
        self.assertEqual(response.status_code, 200)

    def test_collections_list_shows_per_level_entries(self):
        """Test collections list shows separate entries per admin level."""
        response = self.url_open(f"{OGC_BASE}/collections", headers=self._gis_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        collection_ids = [c["id"] for c in data["collections"]]
        # Should have _admN entries for the report
        adm_entries = [cid for cid in collection_ids if cid.startswith("http_test_report_adm")]
        self.assertGreaterEqual(len(adm_entries), 2, "Report with 2 area levels should have at least 2 _admN entries")
