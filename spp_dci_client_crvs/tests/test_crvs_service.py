# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CRVS Service."""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CRVSClientCommon


@tagged("post_install", "-at_install")
class TestCRVSService(CRVSClientCommon):
    """Test cases for CRVS Service."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Create a data source for testing
        self.data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "our_callback_uri": "https://openspp.example.org/callback",
                "registry_type": "CRVS",
            }
        )

    def _get_service(self):
        """Get CRVSService instance."""
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        return CRVSService(self.env, self.data_source.code)

    def test_service_initialization(self):
        """Test CRVSService can be initialized."""
        service = self._get_service()
        self.assertIsNotNone(service)
        self.assertIsNotNone(service.client)

    def test_service_initialization_invalid_code(self):
        """Test CRVSService raises error for invalid data source code."""
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        with self.assertRaises(UserError):
            CRVSService(self.env, "nonexistent_code")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_events_default_types(self, mock_subscribe):
        """Test subscribe_events uses default event types."""
        mock_subscribe.return_value = {"message": {"correlation_id": "test-123"}}

        service = self._get_service()
        result = service.subscribe_events()

        # Should call subscribe twice (for BIRTH and DEATH)
        self.assertEqual(mock_subscribe.call_count, 2)

        # Verify event types
        call_args_list = mock_subscribe.call_args_list
        event_types = [call[1]["event_type"] for call in call_args_list]
        self.assertIn("BIRTH", event_types)
        self.assertIn("DEATH", event_types)

        # Should return list of subscription IDs
        self.assertEqual(len(result), 2)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_events_custom_types(self, mock_subscribe):
        """Test subscribe_events with custom event types."""
        mock_subscribe.return_value = {"message": {"correlation_id": "test-456"}}

        service = self._get_service()
        result = service.subscribe_events(event_types=["MARRIAGE"])

        # Should call subscribe once
        mock_subscribe.assert_called_once()

        # Verify event type
        call_kwargs = mock_subscribe.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "MARRIAGE")

        # Should return one subscription ID
        self.assertEqual(len(result), 1)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_events_handles_failure(self, mock_subscribe):
        """Test subscribe_events handles subscription failures."""
        # First call succeeds, second fails
        mock_subscribe.side_effect = [
            {"message": {"correlation_id": "test-789"}},
            Exception("Network error"),
        ]

        service = self._get_service()

        # Should raise UserError because no subscriptions succeeded after one failed
        with self.assertRaises(UserError):
            service.subscribe_events(event_types=["BIRTH", "DEATH"])

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_events_partial_success(self, mock_subscribe):
        """Test subscribe_events with partial success."""
        # First call succeeds, second returns invalid response
        mock_subscribe.side_effect = [
            {"message": {"correlation_id": "test-111"}},
            {"message": {}},  # No correlation_id
        ]

        service = self._get_service()
        result = service.subscribe_events(event_types=["BIRTH", "DEATH"])

        # Should return only successful subscription
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "test-111")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.unsubscribe")
    def test_unsubscribe_events(self, mock_unsubscribe):
        """Test unsubscribe_events method."""
        mock_unsubscribe.return_value = {"message": {"ack_status": "ACK"}}

        service = self._get_service()
        result = service.unsubscribe_events(subscription_codes=["sub-001", "sub-002"])

        mock_unsubscribe.assert_called_once_with(subscription_codes=["sub-001", "sub-002"])
        self.assertIsNotNone(result)

    def test_unsubscribe_events_validation(self):
        """Test unsubscribe_events validates subscription_codes."""
        service = self._get_service()

        with self.assertRaises(ValidationError):
            service.unsubscribe_events(subscription_codes=[])

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.unsubscribe")
    def test_unsubscribe_events_failure(self, mock_unsubscribe):
        """Test unsubscribe_events handles failures."""
        mock_unsubscribe.side_effect = Exception("API error")

        service = self._get_service()

        with self.assertRaises(UserError):
            service.unsubscribe_events(subscription_codes=["sub-001"])

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_verify_birth(self, mock_search):
        """Test verify_birth method."""
        mock_search.return_value = {
            "message": {
                "search_response": [
                    {
                        "data": [
                            {
                                "name": "John Doe",
                                "birth_date": "1990-01-15",
                            }
                        ]
                    }
                ]
            }
        }

        service = self._get_service()
        result = service.verify_birth("UIN", "12345678")

        # Should call search with correct parameters
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        self.assertEqual(call_kwargs["query_type"], "idtype-value")
        self.assertIn("12345678", call_kwargs["query_value"])

        # Should return birth data
        self.assertIsNotNone(result)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_verify_birth_not_found(self, mock_search):
        """Test verify_birth when no records found."""
        mock_search.return_value = {"message": {"search_response": []}}

        service = self._get_service()
        result = service.verify_birth("UIN", "nonexistent")

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_check_death(self, mock_search):
        """Test check_death method."""
        mock_search.return_value = {
            "message": {
                "search_response": [
                    {
                        "data": [
                            {
                                "death_date": "2024-06-15",
                            }
                        ]
                    }
                ]
            }
        }

        service = self._get_service()
        result = service.check_death("UIN", "12345678")

        # Should return True (deceased)
        self.assertTrue(result)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_check_death_alive(self, mock_search):
        """Test check_death when no death record."""
        mock_search.return_value = {"message": {"search_response": []}}

        service = self._get_service()
        result = service.check_death("UIN", "12345678")

        # Should return False (alive)
        self.assertFalse(result)
