# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for SR Service."""

import uuid
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSRService(TransactionCase):
    """Test cases for SR Service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.Partner = cls.env["res.partner"]

        # Create test data source
        cls.test_data_source = cls.DataSource.create(
            {
                "name": "Test SR Data Source",
                "code": "test_sr",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.test",
                "auth_type": "none",  # Use no auth for testing
                "registry_type": "sr",
                "state": "active",
            }
        )

        # Create test partner
        cls.test_partner = cls.Partner.create(
            {
                "name": "Test Person for SR",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _get_sr_service(self):
        """Create SR service instance."""
        from odoo.addons.spp_dci_client_sr.services import SRService

        return SRService(self.env, "test_sr")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_sync(self, mock_search):
        """Test synchronous person search."""
        mock_search.return_value = {
            "data": {
                "reg_records": [
                    {
                        "id": "PERSON_001",
                        "name": "John Doe",
                        "birth_date": "1990-01-15",
                        "gender": "male",
                    }
                ]
            }
        }

        service = self._get_sr_service()
        result = service.search_person("UIN", "123456789", async_mode=False)

        self.assertIsNotNone(result)
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_async(self, mock_search):
        """Test asynchronous person search."""
        txn_id = str(uuid.uuid4())
        mock_search.return_value = {"transaction_id": txn_id}

        service = self._get_sr_service()
        result = service.search_person("UIN", "123456789", async_mode=True)

        self.assertIsNotNone(result)
        self.assertEqual(result.get("transaction_id"), txn_id)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_household(self, mock_search):
        """Test household search."""
        mock_search.return_value = {
            "data": {
                "reg_records": [
                    {"id": "MEMBER_001", "name": "Member 1", "household_id": "HH_001"},
                    {"id": "MEMBER_002", "name": "Member 2", "household_id": "HH_001"},
                ]
            }
        }

        service = self._get_sr_service()
        result = service.search_household("HH_001")

        self.assertIsNotNone(result)
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_get_program_enrollment(self, mock_search):
        """Test getting program enrollment data."""
        mock_search.return_value = {
            "data": {
                "reg_records": [
                    {
                        "id": "PERSON_001",
                        "enrolled_programs": ["Cash Transfer", "Food Assistance"],
                    }
                ]
            }
        }

        service = self._get_sr_service()
        result = service.get_program_enrollment("UIN", "123456789")

        self.assertIsNotNone(result)
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_updates(self, mock_subscribe):
        """Test subscribing to SR updates."""
        mock_subscribe.return_value = {"subscription_id": "SUB_001"}

        service = self._get_sr_service()
        result = service.subscribe_updates(event_types=["ENROLLMENT", "UPDATE"])

        self.assertIsNotNone(result)
        mock_subscribe.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_new_record(self, mock_search):
        """Test syncing person data to local record - creates new record."""
        mock_search.return_value = {
            "data": {
                "reg_records": [
                    {
                        "id": "EXT_001",
                        "name": "Synced Person",
                        "birth_date": "1985-03-20",
                        "gender": "female",
                        "enrolled_programs": ["Program A"],
                        "household_id": "HH_100",
                        "household_size": 4,
                        "is_head_of_household": True,
                    }
                ]
            }
        }

        service = self._get_sr_service()
        result = service.sync_person_to_local("UIN", "SYNC_001", partner_id=self.test_partner.id)

        self.assertIsNotNone(result)

        # Check SR record was created
        sr_record = self.env["spp.dci.sr.record"].search([("partner_id", "=", self.test_partner.id)])
        self.assertTrue(sr_record)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_update_record(self, mock_search):
        """Test syncing person data to local record - updates existing record."""
        # Create existing SR record
        self.env["spp.dci.sr.record"].create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT_002",
                "source_registry": self.test_data_source.code,
                "sr_name": "Old Name",
                "state": "synced",
            }
        )

        mock_search.return_value = {
            "data": {
                "reg_records": [
                    {
                        "id": "EXT_002",
                        "name": "Updated Name",
                        "enrolled_programs": ["Program B"],
                    }
                ]
            }
        }

        service = self._get_sr_service()
        result = service.sync_person_to_local("UIN", "SYNC_002", partner_id=self.test_partner.id)

        self.assertIsNotNone(result)

        # Check SR record was updated
        sr_record = self.env["spp.dci.sr.record"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("source_registry", "=", self.test_data_source.code),
            ]
        )
        self.assertEqual(sr_record.sr_name, "Updated Name")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_no_results(self, mock_search):
        """Test syncing person when no results returned."""
        mock_search.return_value = {"data": {"reg_records": []}}

        service = self._get_sr_service()
        result = service.sync_person_to_local("UIN", "NOT_FOUND")

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_error_handling(self, mock_search):
        """Test error handling in search."""
        mock_search.side_effect = Exception("API Error")

        service = self._get_sr_service()
        result = service.search_person("UIN", "123456789")

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_check_connection(self, mock_search):
        """Test check_connection method."""
        mock_search.return_value = {"message": {"status": "ok"}}

        service = self._get_sr_service()
        result = service.check_connection()

        self.assertTrue(result)
        mock_search.assert_called_once()

    def test_service_initialization(self):
        """Test service initialization with data source."""
        service = self._get_sr_service()

        self.assertEqual(service.data_source.code, "test_sr")
        self.assertEqual(service.env, self.env)
        self.assertIsNotNone(service.client)
