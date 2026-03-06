# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI birth verification in Add Member change request."""

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBirthVerification(TransactionCase):
    """Test birth verification via DCI in Add Member CR."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.CRDetail = cls.env["spp.cr.detail.add_member"]

        # Create a test data source
        cls.data_source = cls.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "registry_type": "ns:org:RegistryType:Civil",
                "active": True,
            }
        )

        # Get or create a group for testing
        cls.test_group = cls.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Get or create a change request type
        cls.request_type = cls.env["spp.change.request.type"].search([("code", "=", "add_member")], limit=1)
        if not cls.request_type:
            cls.request_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Add Member",
                    "code": "add_member",
                    "detail_model": "spp.cr.detail.add_member",
                    "strategy_model": "spp.cr.apply.add_member",
                }
            )

    def _create_test_cr_detail(self, **kwargs):
        """Helper to create a test CR detail record."""
        # Create a change request first
        cr = self.env["spp.change.request"].create(
            {
                "registrant_id": self.test_group.id,
                "request_type_id": self.request_type.id,
            }
        )

        # Create detail record
        detail_vals = {
            "registrant_id": self.test_group.id,
            "change_request_id": cr.id,
            "given_name": "Test",
            "family_name": "Child",
            "member_name": "CHILD, TEST",
        }
        detail_vals.update(kwargs)
        detail = self.CRDetail.create(detail_vals)

        # Link the detail to the CR
        cr.write({"detail_res_id": detail.id})

        return detail

    def test_birth_verification_fields_exist(self):
        """Test that DCI birth verification fields are present on CR detail."""
        detail = self._create_test_cr_detail()

        # Check field existence
        self.assertIn("birth_registration_number", detail._fields)
        self.assertIn("birth_verification_status", detail._fields)
        self.assertIn("birth_verification_date", detail._fields)
        self.assertIn("birth_verification_response", detail._fields)
        self.assertIn("dci_data_source_id", detail._fields)

    def test_birth_verification_default_status(self):
        """Test default verification status is 'unverified'."""
        detail = self._create_test_cr_detail()
        self.assertEqual(detail.birth_verification_status, "unverified")

    def test_action_verify_birth_requires_brn(self):
        """Test verify action fails without BRN."""
        detail = self._create_test_cr_detail()

        with self.assertRaises(UserError) as cm:
            detail.action_verify_birth()
        self.assertIn("Birth Registration Number", str(cm.exception))

    def test_action_verify_birth_requires_data_source(self):
        """Test verify action fails without data source."""
        # Deactivate all CRVS data sources
        self.DataSource.search(
            [
                ("registry_type", "=", "ns:org:RegistryType:Civil"),
            ]
        ).write({"active": False})

        detail = self._create_test_cr_detail(
            birth_registration_number="TEST123",
        )

        with self.assertRaises(UserError) as cm:
            detail.action_verify_birth()
        self.assertIn("data source", str(cm.exception).lower())

        # Re-activate for other tests
        self.data_source.active = True

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_action_verify_birth_success_direct_response(self, mock_client_class):
        """Test successful verification with OpenCRVS direct response format."""
        # Mock DCI client response (OpenCRVS format)
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "identifier": [
                {"identifier_type": "UIN", "identifier_value": "5126797337"},
                {"identifier_type": "BRN", "identifier_value": "UP7D57VSEAZM"},
            ],
            "name": {"given_name": "George", "second_name": "", "surname": "Smith"},
            "sex": "male",
            "birth_date": "2026-02-05",
        }
        mock_client_class.return_value = mock_client

        detail = self._create_test_cr_detail(
            birth_registration_number="UP7D57VSEAZM",
            dci_data_source_id=self.data_source.id,
        )

        result = detail.action_verify_birth()

        # Verify status updated
        self.assertEqual(detail.birth_verification_status, "verified")
        self.assertTrue(detail.birth_verification_date)
        self.assertTrue(detail.birth_verification_response)

        # Verify response is stored as JSON
        response_data = json.loads(detail.birth_verification_response)
        self.assertIn("identifier", response_data)

        # Verify notification is returned
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_action_verify_birth_success_dci_format(self, mock_client_class):
        """Test successful verification with standard DCI response format."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "header": {"status": "succ"},
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": [
                            {
                                "identifier": [{"type": "BRN", "value": "TEST123"}],
                                "name": {"given_name": "Test"},
                            }
                        ],
                    }
                ]
            },
        }
        mock_client_class.return_value = mock_client

        detail = self._create_test_cr_detail(
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )

        detail.action_verify_birth()

        self.assertEqual(detail.birth_verification_status, "verified")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_action_verify_birth_not_found(self, mock_client_class):
        """Test verification with no matching record."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": [],
                    }
                ]
            },
        }
        mock_client_class.return_value = mock_client

        detail = self._create_test_cr_detail(
            birth_registration_number="NONEXISTENT",
            dci_data_source_id=self.data_source.id,
        )

        result = detail.action_verify_birth()

        self.assertEqual(detail.birth_verification_status, "not_found")
        self.assertEqual(result["params"]["type"], "warning")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_action_verify_birth_error(self, mock_client_class):
        """Test verification with API error."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        detail = self._create_test_cr_detail(
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )

        with self.assertRaises(UserError) as cm:
            detail.action_verify_birth()

        self.assertIn("API Error", str(cm.exception))
        # Note: The status update is rolled back with the transaction when exception is raised
        # So we only verify the exception message, not the status

    def test_get_default_dci_data_source(self):
        """Test getting default DCI data source."""
        detail = self._create_test_cr_detail()

        default_source = detail._get_default_dci_data_source()

        # Should find our test data source
        self.assertTrue(default_source)
        self.assertEqual(default_source.registry_type, "ns:org:RegistryType:Civil")
        self.assertTrue(default_source.active)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient")
    def test_parse_dci_response_error_status(self, mock_client_class):
        """Test parsing response with error status in header."""
        mock_client = MagicMock()
        mock_client.search_by_id_opencrvs.return_value = {
            "header": {"status": "rjct"},
            "message": {},
        }
        mock_client_class.return_value = mock_client

        detail = self._create_test_cr_detail(
            birth_registration_number="TEST123",
            dci_data_source_id=self.data_source.id,
        )

        detail.action_verify_birth()

        self.assertEqual(detail.birth_verification_status, "error")
