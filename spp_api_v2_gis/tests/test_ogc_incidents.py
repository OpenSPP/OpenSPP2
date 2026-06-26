# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OGC API - Features: Incidents collection.

Tests cover:
- Collection discovery and metadata
- GET items with filters (event, severity, status, datetime, bbox)
- GET single item by UUID
- POST (create incident from alert)
- PUT (update incident)
- Duplicate detection (409 Conflict)
- Scope enforcement
"""

import json
import logging

from odoo.exceptions import MissingError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)

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

SAMPLE_POLYGON_2 = {
    "type": "Polygon",
    "coordinates": [
        [
            [102.0, 2.0],
            [103.0, 2.0],
            [103.0, 3.0],
            [102.0, 3.0],
            [102.0, 2.0],
        ]
    ],
}


@tagged("post_install", "-at_install")
class TestOGCIncidentRead(TransactionCase):
    """Read path tests for incidents OGC collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        VocabCode = cls.env["spp.vocabulary.code"]
        cls.severity_extreme = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "extreme")
        cls.severity_severe = VocabCode.get_code("urn:oasis:names:tc:cap:severity", "severe")

        Incident = cls.env["spp.hazard.incident"]

        # Create incidents via create_from_alert for realistic test data
        cls.incident1 = Incident.create_from_alert(
            SAMPLE_POLYGON,
            {
                "event": "Flood",
                "headline": "OGC Test Flood",
                "severity": "extreme",
                "urgency": "immediate",
                "source": "Test Agency",
                "source_alert_id": "OGC-INC-001",
                "effective": "2026-04-01T00:00:00Z",
                "expires": "2026-04-15T00:00:00Z",
            },
        )

        cls.incident2 = Incident.create_from_alert(
            SAMPLE_POLYGON_2,
            {
                "event": "Drought",
                "headline": "OGC Test Drought",
                "severity": "severe",
                "source_alert_id": "OGC-INC-002",
                "effective": "2026-03-01T00:00:00Z",
            },
        )

    def _make_service(self, base_url="http://localhost:8069/api/v2/spp"):
        from ..services.ogc_service import OGCService

        return OGCService(self.env, base_url)

    # --- Collection discovery ---

    def test_collections_includes_incidents(self):
        """GET /collections must include an 'incidents' collection."""
        service = self._make_service()
        result = service.get_collections()

        ids = [c["id"] for c in result["collections"]]
        self.assertIn("incidents", ids)

    def test_incidents_collection_has_items_link(self):
        """Incidents collection must have an 'items' link."""
        service = self._make_service()
        collection = service.get_collection("incidents")

        link_rels = [link["rel"] for link in collection["links"]]
        self.assertIn("items", link_rels)
        self.assertIn("self", link_rels)

    # --- _parse_collection_id ---

    def test_parse_collection_id_incidents(self):
        """'incidents' must parse as ('incident', None, None)."""
        service = self._make_service()
        layer_type, layer_id, admin_level = service._parse_collection_id("incidents")

        self.assertEqual(layer_type, "incident")
        self.assertIsNone(layer_id)
        self.assertIsNone(admin_level)

    # --- GET items ---

    def test_get_items_returns_feature_collection(self):
        """GET items returns GeoJSON FeatureCollection."""
        service = self._make_service()
        result = service.get_collection_items("incidents")

        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("numberMatched", result)
        self.assertGreaterEqual(result["numberMatched"], 2)

    def test_get_items_features_have_top_level_id(self):
        """Each feature must have a top-level 'id' (UUID)."""
        service = self._make_service()
        result = service.get_collection_items("incidents")

        for feature in result["features"]:
            self.assertIn("id", feature)
            self.assertIsNotNone(feature["id"])

    def test_get_items_features_have_cap_properties(self):
        """Features must include CAP-aligned properties."""
        service = self._make_service()
        result = service.get_collection_items("incidents")

        self.assertGreater(len(result["features"]), 0)
        props = result["features"][0]["properties"]

        expected_keys = ["code", "event", "severity", "headline", "status"]
        for key in expected_keys:
            self.assertIn(key, props, f"Missing property: {key}")

    def test_get_items_filter_by_event(self):
        """event filter returns only matching incidents."""
        service = self._make_service()
        result = service.get_collection_items("incidents", event="Flood")

        for feature in result["features"]:
            self.assertEqual(feature["properties"]["event"], "Flood")

    def test_get_items_filter_by_severity(self):
        """severity filter returns only matching incidents."""
        service = self._make_service()
        result = service.get_collection_items("incidents", severity="extreme")

        for feature in result["features"]:
            self.assertEqual(feature["properties"]["severity"], "extreme")

    def test_get_items_filter_by_status(self):
        """status filter returns only matching incidents."""
        service = self._make_service()
        result = service.get_collection_items("incidents", incident_status="active")

        for feature in result["features"]:
            self.assertEqual(feature["properties"]["status"], "active")

    def test_get_items_pagination(self):
        """GET items respects limit and offset."""
        service = self._make_service()
        result = service.get_collection_items("incidents", limit=1, offset=0)

        self.assertEqual(result["numberReturned"], 1)
        self.assertGreaterEqual(result["numberMatched"], 2)

    # --- GET single item ---

    def test_get_item_by_uuid(self):
        """GET single item by UUID returns the correct feature."""
        service = self._make_service()
        feature = service.get_collection_item("incidents", self.incident1.uuid)

        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["id"], self.incident1.uuid)
        self.assertEqual(feature["properties"]["headline"], "OGC Test Flood")

    def test_get_item_has_geometry(self):
        """GET single item has geometry from linked geofence."""
        service = self._make_service()
        feature = service.get_collection_item("incidents", self.incident1.uuid)

        self.assertIsNotNone(feature["geometry"])
        self.assertEqual(feature["geometry"]["type"], "Polygon")

    def test_get_item_nonexistent_returns_404(self):
        """GET single item with bad UUID returns MissingError."""
        service = self._make_service()

        with self.assertRaises(MissingError):
            service.get_collection_item("incidents", "nonexistent-uuid-12345")


@tagged("post_install", "-at_install")
class TestOGCIncidentWrite(TransactionCase):
    """Write path tests for incidents OGC collection."""

    def _make_service(self, base_url="http://localhost:8069/api/v2/spp"):
        from ..services.ogc_service import OGCService

        return OGCService(self.env, base_url)

    # --- POST (create) ---

    def test_post_creates_incident(self):
        """POST creates an incident and returns 201-style result."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "event": "Flood",
                "headline": "OGC POST Test Flood",
                "severity": "extreme",
                "source_alert_id": "POST-TEST-001",
            },
        }

        result = service.create_incident_feature(feature_input)

        self.assertEqual(result["feature"]["type"], "Feature")
        self.assertIn("id", result["feature"])
        self.assertEqual(result["feature"]["properties"]["headline"], "OGC POST Test Flood")
        self.assertIsNotNone(result["location"])

    def test_post_missing_geometry_returns_error(self):
        """POST without geometry raises ValueError."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "event": "Flood",
                "headline": "No Geometry Test",
            },
        }

        with self.assertRaises(ValueError):
            service.create_incident_feature(feature_input)

    def test_post_duplicate_source_alert_id_returns_409(self):
        """POST with existing source_alert_id raises DuplicateAlertError."""
        from ..services.ogc_service import DuplicateAlertError

        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "event": "Flood",
                "headline": "First Alert",
                "source_alert_id": "DUP-TEST-001",
            },
        }

        # First POST succeeds
        result = service.create_incident_feature(feature_input)
        self.assertIsNotNone(result["feature"])

        # Second POST with same source_alert_id returns 409
        feature_input["properties"]["headline"] = "Duplicate Alert"
        with self.assertRaises(DuplicateAlertError) as cm:
            service.create_incident_feature(feature_input)

        self.assertIn("DUP-TEST-001", str(cm.exception))
        self.assertIsNotNone(cm.exception.location)

    # --- PUT (update) ---

    def test_put_updates_incident(self):
        """PUT updates incident properties."""
        service = self._make_service()

        # Create first
        create_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "event": "Storm",
                "headline": "Initial Storm",
                "source_alert_id": "PUT-TEST-001",
            },
        }
        create_result = service.create_incident_feature(create_input)
        uuid = create_result["feature"]["id"]

        # Update
        update_input = {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "event": "Storm",
                "headline": "Updated Storm",
                "severity": "extreme",
            },
        }
        result = service.replace_incident_feature(uuid, update_input)

        self.assertEqual(result["properties"]["headline"], "Updated Storm")
        self.assertEqual(result["properties"]["severity"], "extreme")

    def test_put_with_geometry_updates_geofence(self):
        """PUT with geometry updates the linked geofence."""
        service = self._make_service()

        create_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "event": "Storm",
                "headline": "Geometry Update Test",
                "source_alert_id": "PUT-GEO-001",
            },
        }
        create_result = service.create_incident_feature(create_input)
        uuid = create_result["feature"]["id"]

        # Update with new geometry
        update_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON_2,
            "properties": {
                "event": "Storm",
                "headline": "Geometry Updated",
            },
        }
        result = service.replace_incident_feature(uuid, update_input)

        self.assertIsNotNone(result["geometry"])

    def test_put_nonexistent_returns_404(self):
        """PUT on nonexistent UUID raises MissingError."""
        service = self._make_service()
        update_input = {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "event": "Storm",
                "headline": "Not Found",
            },
        }

        with self.assertRaises(MissingError):
            service.replace_incident_feature("nonexistent-uuid-99999", update_input)


@tagged("post_install", "-at_install")
class TestOGCDatetimeParsing(TransactionCase):
    """Tests for OGC datetime parameter parsing."""

    def _make_service(self):
        from ..services.ogc_service import OGCService

        return OGCService(self.env)

    def test_instant(self):
        """Single datetime returns same value for start and end."""
        service = self._make_service()
        start, end = service._parse_datetime_param("2026-04-01T00:00:00Z")
        self.assertEqual(start, "2026-04-01T00:00:00Z")
        self.assertEqual(end, "2026-04-01T00:00:00Z")

    def test_bounded_interval(self):
        """start/end returns both values."""
        service = self._make_service()
        start, end = service._parse_datetime_param("2026-01-01/2026-06-01")
        self.assertEqual(start, "2026-01-01")
        self.assertEqual(end, "2026-06-01")

    def test_open_start(self):
        """../end returns None for start."""
        service = self._make_service()
        start, end = service._parse_datetime_param("../2026-06-01")
        self.assertIsNone(start)
        self.assertEqual(end, "2026-06-01")

    def test_open_end(self):
        """start/.. returns None for end."""
        service = self._make_service()
        start, end = service._parse_datetime_param("2026-01-01/..")
        self.assertEqual(start, "2026-01-01")
        self.assertIsNone(end)


@tagged("post_install", "-at_install")
class TestIncidentScopeEnforcement(TransactionCase):
    """Tests that scope checks block or allow incident write operations."""

    def _make_client(self, scopes):
        """Create an spp.api.client record with the given scopes.

        Args:
            scopes: List of {"resource": str, "action": str} dicts

        Returns:
            spp.api.client record
        """
        partner = self.env["res.partner"].create({"name": "Scope Test Org"})
        org_type = self.env.ref("spp_consent.org_type_government", raise_if_not_found=False)
        if not org_type:
            org_type = self.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not org_type:
            org_type = self.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})
        client = self.env["spp.api.client"].create(
            {
                "name": "Scope Test Client",
                "partner_id": partner.id,
                "organization_type_id": org_type.id,
            }
        )
        for scope_def in scopes:
            self.env["spp.api.client.scope"].create(
                {
                    "client_id": client.id,
                    "resource": scope_def["resource"],
                    "action": scope_def["action"],
                }
            )
        return client

    def test_gis_read_scope_cannot_post_incident(self):
        """A client with only gis:read scope must be denied gis:incident write access."""
        from fastapi import HTTPException

        from ..routers.ogc_features import _check_gis_incident_scope

        client = self._make_client([{"resource": "gis", "action": "read"}])

        self.assertFalse(client.has_scope("gis", "incident"))
        with self.assertRaises(HTTPException) as cm:
            _check_gis_incident_scope(client)
        self.assertEqual(cm.exception.status_code, 403)

    def test_gis_geofence_scope_cannot_post_incident(self):
        """A client with only gis:geofence scope must be denied gis:incident write access."""
        from fastapi import HTTPException

        from ..routers.ogc_features import _check_gis_incident_scope

        client = self._make_client([{"resource": "gis", "action": "geofence"}])

        self.assertFalse(client.has_scope("gis", "incident"))
        with self.assertRaises(HTTPException) as cm:
            _check_gis_incident_scope(client)
        self.assertEqual(cm.exception.status_code, 403)

    def test_gis_incident_scope_allows_post_incident(self):
        """A client with gis:incident scope must pass the incident scope check."""
        from ..routers.ogc_features import _check_gis_incident_scope

        client = self._make_client([{"resource": "gis", "action": "incident"}])

        self.assertTrue(client.has_scope("gis", "incident"))
        # Must not raise
        _check_gis_incident_scope(client)


@tagged("post_install", "-at_install")
class TestOGCGeofenceIncidentFilter(TransactionCase):
    """Tests for incident_code filter on geofences collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Incident = cls.env["spp.hazard.incident"]

        cls.incident = Incident.create_from_alert(
            SAMPLE_POLYGON,
            {
                "event": "Flood",
                "headline": "Geofence Filter Test",
                "source_alert_id": "GF-FILTER-001",
            },
        )

        # Create an unrelated geofence
        cls.env["spp.gis.geofence"].create(
            {
                "name": "Unrelated Geofence",
                "geometry": json.dumps(SAMPLE_POLYGON_2),
                "geofence_type": "custom",
            }
        )

    def _make_service(self, base_url="http://localhost:8069/api/v2/spp"):
        from ..services.ogc_service import OGCService

        return OGCService(self.env, base_url)

    def test_incident_code_filter_returns_linked_geofences(self):
        """incident_code filter returns only geofences linked to that incident."""
        service = self._make_service()
        result = service.get_collection_items("geofences", incident_code="GF-FILTER-001")

        self.assertGreaterEqual(result["numberReturned"], 1)
        for feature in result["features"]:
            # All returned geofences should have hazard_zone type
            self.assertEqual(feature["properties"]["geofence_type"], "hazard_zone")

    def test_incident_code_filter_no_match_returns_empty(self):
        """incident_code filter with nonexistent code returns empty collection."""
        service = self._make_service()
        result = service.get_collection_items("geofences", incident_code="NONEXISTENT-CODE")

        self.assertEqual(result["numberReturned"], 0)
