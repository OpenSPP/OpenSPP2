# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration tests for DCI CEL integration with mock DCI server.

These tests require the mock_registry Docker service to be running.
Run with: invoke dci-compliance --registry=client-compliance

The mock server provides:
- /registry/sync/search - Sync search endpoint
- /registry/search - Async search (returns ACK, sends callback)
- /registry/subscribe - Subscribe endpoint
- /admin/* - Admin API for test control
"""

import os
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def mock_registry_available():
    """Check if mock registry is available."""
    url = os.environ.get("MOCK_REGISTRY_URL", "http://mock_registry:3335")
    try:
        resp = requests.get(f"{url}/admin/healthcheck", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


@tagged("post_install", "-at_install", "dci_integration")
class TestDCIClientIntegration(TransactionCase):
    """Integration tests for DCIClient with mock DCI server.

    These tests are skipped if mock_registry is not available.
    To run: start mock_registry service first.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.mock_url = os.environ.get("MOCK_REGISTRY_URL", "http://mock_registry:3335")
        cls.skip_integration = not mock_registry_available()

        if cls.skip_integration:
            return

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Integration Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create ID for partner
        cls.id_type = cls.env["spp.id.type"].create(
            {
                "name": "Test UIN",
                "code": "UIN",
            }
        )
        cls.env["spp.id"].create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": cls.id_type.id,
                "value": "UIN-INTEGRATION-001",
            }
        )

        # Create data sources pointing to mock registry
        cls.sr_data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Mock Social Registry",
                "code": "mock_sr",
                "base_url": cls.mock_url,
                "auth_type": "bearer",
                "bearer_token": "integration-test-token",
                "our_sender_id": "openspp.integration.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "registry_type": "social",
                "state": "active",
            }
        )

        cls.dr_data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Mock Disability Registry",
                "code": "mock_dr",
                "base_url": cls.mock_url,
                "auth_type": "bearer",
                "bearer_token": "integration-test-token",
                "our_sender_id": "openspp.integration.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "registry_type": "dr",
                "state": "active",
            }
        )

    def setUp(self):
        """Reset mock server before each test."""
        super().setUp()
        if self.skip_integration:
            self.skipTest("Mock registry not available")

        # Reset mock server recordings
        try:
            requests.post(f"{self.mock_url}/admin/reset", timeout=2)
        except Exception:
            pass

    def test_dci_client_sync_search(self):
        """Test DCIClient sync search against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform sync search
        result = client.search(
            query_type="idtype-value",
            query_value="UIN:TEST-001",
            record_type="PERSON",
        )

        # Verify response structure
        self.assertIn("message", result)
        self.assertIn("search_response", result["message"])

        # Verify request was recorded
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

        # Verify request structure
        last_request = recordings["requests"][-1]
        self.assertEqual(last_request["action"], "search")
        self.assertIn("Authorization", last_request["headers"])

    def test_dci_client_async_search(self):
        """Test DCIClient async search against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform async search
        result = client.search_async(
            query_type="idtype-value",
            query_value="UIN:TEST-002",
            record_type="PERSON",
        )

        # Verify ACK response
        self.assertIn("message", result)
        self.assertEqual(result["message"]["ack_status"], "ACK")
        self.assertIn("correlation_id", result["message"])

        # Verify request was recorded
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/search", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

    def test_dci_client_subscribe(self):
        """Test DCIClient subscribe against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform subscribe
        result = client.subscribe(
            event_type="REGISTER",
            notify_record_type="Person",
        )

        # Verify ACK response
        self.assertIn("message", result)
        self.assertEqual(result["message"]["ack_status"], "ACK")

        # Verify request was recorded
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/subscribe", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

        # Verify subscribe_request structure
        last_request = recordings["requests"][-1]
        self.assertIn("subscribe_request", last_request["body"]["message"])

    def test_dci_client_unsubscribe(self):
        """Test DCIClient unsubscribe against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform unsubscribe
        result = client.unsubscribe(subscription_codes=["sub-001", "sub-002"])

        # Verify ACK response
        self.assertIn("message", result)
        self.assertEqual(result["message"]["ack_status"], "ACK")

        # Verify request was recorded
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/unsubscribe", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

    def test_dci_client_txn_status(self):
        """Test DCIClient txn_status against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform txn status check
        result = client.txn_status(
            attribute_value="txn-12345",
            attribute_type="transaction_id",
        )

        # Verify ACK response
        self.assertIn("message", result)
        self.assertEqual(result["message"]["ack_status"], "ACK")

        # Verify request was recorded
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/txn/status", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

    def test_dci_client_search_by_predicate(self):
        """Test DCIClient search_by_predicate (CEL) against mock server."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)

        # Perform predicate search (CEL expression)
        result = client.search_by_predicate(
            predicate="person.age >= 18 && person.status == 'active'",
            record_type="PERSON",
            async_mode=False,  # Use sync for easier assertion
        )

        # Verify response
        self.assertIn("message", result)

        # Verify request was recorded with predicate query_type
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()

        last_request = recordings["requests"][-1]
        search_criteria = last_request["body"]["message"]["search_request"][0]["search_criteria"]
        self.assertEqual(search_criteria["query_type"], "predicate")

    def test_dci_client_bearer_auth(self):
        """Test DCIClient sends Bearer token in headers."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)
        client.search(query_type="idtype-value", query_value="UIN:AUTH-TEST")

        # Verify Authorization header
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()

        last_request = recordings["requests"][-1]
        self.assertIn("authorization", last_request["headers"])
        self.assertTrue(
            last_request["headers"]["authorization"].startswith("Bearer "),
            "Authorization header should use Bearer scheme",
        )

    def test_dci_client_envelope_meta(self):
        """Test DCIClient includes meta field in header."""
        from odoo.addons.spp_dci_client.services.client import DCIClient

        client = DCIClient(self.sr_data_source, self.env)
        client.search(query_type="idtype-value", query_value="UIN:META-TEST")

        # Verify meta field in header
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()

        last_request = recordings["requests"][-1]
        self.assertIn("meta", last_request["body"]["header"])


@tagged("post_install", "-at_install", "dci_integration")
class TestDRServiceIntegration(TransactionCase):
    """Integration tests for DRService with mock DCI server."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.mock_url = os.environ.get("MOCK_REGISTRY_URL", "http://mock_registry:3335")
        cls.skip_integration = not mock_registry_available()

        if cls.skip_integration:
            return

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "DR Integration Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create ID for partner
        cls.id_type = cls.env["spp.id.type"].create(
            {
                "name": "Test UIN DR",
                "code": "UIN",
            }
        )
        cls.env["spp.id"].create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": cls.id_type.id,
                "value": "UIN-DR-INTEGRATION-001",
            }
        )

        # Create DR data source pointing to mock registry
        cls.dr_data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Mock DR Integration",
                "code": "mock_dr_int",
                "base_url": cls.mock_url,
                "auth_type": "bearer",
                "bearer_token": "dr-integration-token",
                "our_sender_id": "openspp.dr.test",
                "registry_type": "dr",
                "state": "active",
            }
        )

    def setUp(self):
        """Reset mock server before each test."""
        super().setUp()
        if self.skip_integration:
            self.skipTest("Mock registry not available")

        try:
            requests.post(f"{self.mock_url}/admin/reset", timeout=2)
        except Exception:
            pass

    def test_dr_service_get_disability_status_live(self):
        """Test DRService.get_disability_status with mock server."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        service = DRService(self.env, data_source_code="mock_dr_int")

        # Call the service - mock returns empty search_response
        result = service.get_disability_status(self.partner)

        # Mock server returns empty results, so result should be None
        self.assertIsNone(result)

        # Verify request was made
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

    def test_dr_service_sync_creates_status_record(self):
        """Test DRService.sync_disability_data creates status record."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        service = DRService(self.env, data_source_code="mock_dr_int")

        # Sync data
        result = service.sync_disability_data(self.partner)

        self.assertTrue(result)

        # Verify status record was created
        status = self.env["spp.dci.disability.status"].search([("partner_id", "=", self.partner.id)])
        self.assertEqual(len(status), 1)
        self.assertEqual(status.state, "synced")


@tagged("post_install", "-at_install", "dci_integration")
class TestCRVSServiceIntegration(TransactionCase):
    """Integration tests for CRVSService with mock DCI server."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.mock_url = os.environ.get("MOCK_REGISTRY_URL", "http://mock_registry:3335")
        cls.skip_integration = not mock_registry_available()

        if cls.skip_integration:
            return

        # Create CRVS data source pointing to mock registry
        cls.crvs_data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Mock CRVS Integration",
                "code": "mock_crvs_int",
                "base_url": cls.mock_url,
                "auth_type": "bearer",
                "bearer_token": "crvs-integration-token",
                "our_sender_id": "openspp.crvs.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "registry_type": "crvs",
                "state": "active",
            }
        )

    def setUp(self):
        """Reset mock server before each test."""
        super().setUp()
        if self.skip_integration:
            self.skipTest("Mock registry not available")

        try:
            requests.post(f"{self.mock_url}/admin/reset", timeout=2)
        except Exception:
            pass

    def test_crvs_service_subscribe_live(self):
        """Test CRVSService.subscribe_events with mock server."""
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        service = CRVSService(self.env, "mock_crvs_int")

        # Subscribe to events
        result = service.subscribe_events(event_types=["BIRTH"])

        # Should return subscription IDs
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # Verify request was made
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/subscribe", timeout=2).json()
        self.assertGreater(recordings["count"], 0)

    def test_crvs_service_verify_birth_live(self):
        """Test CRVSService.verify_birth with mock server."""
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        service = CRVSService(self.env, "mock_crvs_int")

        # Verify birth - mock returns empty results
        result = service.verify_birth("UIN", "TEST-BIRTH-001")

        # Mock server returns empty data, so result should be None
        self.assertIsNone(result)

        # Verify request was made
        recordings = requests.get(f"{self.mock_url}/admin/requests//registry/sync/search", timeout=2).json()
        self.assertGreater(recordings["count"], 0)
