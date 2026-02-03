# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DRService."""

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDRService(TransactionCase):
    """Tests for DRService."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Partner = cls.env["res.partner"]
        cls.DisabilityStatus = cls.env["spp.dci.disability.status"]
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Get or create ID type vocabulary
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        # Create test ID type codes (is_local=True for test data)
        cls.id_type_uin = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "UIN_DR_TEST",
                "display": "Universal Identification Number",
                "target_type": "individual",
                "is_local": True,
            }
        )
        cls.id_type_drn = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "DRN_TEST",
                "display": "Disability Registration Number",
                "target_type": "individual",
                "is_local": True,
            }
        )

        # Create test partner with identifiers
        cls.partner = cls.Partner.create(
            {
                "name": "Test PWD Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create ID records (spp.registry.id model)
        cls.IdRecord = cls.env["spp.registry.id"]
        cls.id_record = cls.IdRecord.create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-TEST-12345",
            }
        )

        # Create mock data source (auth_type=none for tests)
        cls.data_source = cls.DataSource.create(
            {
                "name": "Test DR Registry",
                "code": "dr_test",
                "registry_type": "DR",
                "base_url": "https://dr.test.gov/api/v1",
                "auth_type": "none",
                "active": True,
            }
        )

    def _create_mock_response(
        self,
        has_disability=True,
        disability_types=None,
        functional_scores=None,
        assessment_date="2024-11-15",
    ):
        """Helper to create mock DR search response."""
        if disability_types is None:
            disability_types = ["Vision", "Mobility"]
        if functional_scores is None:
            functional_scores = {
                "Vision": 3,
                "Hearing": 1,
                "Mobility": 4,
                "Cognition": 1,
                "SelfCare": 2,
                "Communication": 1,
            }

        return {
            "message": {
                "search_response": [
                    {
                        "reference_id": "ref-001",
                        "status": "succ",
                        "data": [
                            {
                                "has_disability": has_disability,
                                "is_pwd": has_disability,
                                "disability_types": disability_types,
                                "functional_scores": functional_scores,
                                "assessment_date": assessment_date,
                                "source_registry": "National DR",
                            }
                        ],
                    }
                ]
            }
        }

    def test_service_init_validates_registry_type(self):
        """Test DRService validates data source registry type."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create non-DR data source
        self.DataSource.create(
            {
                "name": "Wrong Registry",
                "code": "wrong_test",
                "registry_type": "SOCIAL_REGISTRY",  # Not DR
                "base_url": "https://wrong.test.gov/api/v1",
                "auth_type": "none",
                "active": True,
            }
        )

        with self.assertRaises(ValidationError) as cm:
            DRService(self.env, data_source_code="wrong_test")

        self.assertIn("not a Disability Registry", str(cm.exception))

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_success(self, mock_client_class):
        """Test successful disability status retrieval."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Setup mock
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertTrue(result["has_disability"])
        self.assertIn("Vision", result["disability_types"])
        self.assertIn("Mobility", result["disability_types"])
        self.assertEqual(result["functional_scores"]["Vision"], 3)
        self.assertEqual(result["functional_scores"]["Mobility"], 4)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_no_partner(self, mock_client_class):
        """Test get_disability_status raises for no partner."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client_class.return_value = MagicMock()
        service = DRService(self.env, data_source_code="dr_test")

        with self.assertRaises(ValidationError):
            service.get_disability_status(None)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_no_identifier(self, mock_client_class):
        """Test get_disability_status returns None for partner without identifiers."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create partner without identifiers
        partner_no_id = self.Partner.create(
            {
                "name": "No ID Person",
                "is_registrant": True,
            }
        )

        mock_client_class.return_value = MagicMock()
        service = DRService(self.env, data_source_code="dr_test")

        result = service.get_disability_status(partner_no_id)

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_no_results(self, mock_client_class):
        """Test get_disability_status returns None when no DR record found."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Mock empty response
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = {"message": {"search_response": []}}
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_api_error(self, mock_client_class):
        """Test get_disability_status handles API errors."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Mock API error
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = Exception("API connection failed")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")

        with self.assertRaises(UserError) as cm:
            service.get_disability_status(self.partner)

        self.assertIn("Failed to get disability status", str(cm.exception))

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_functional_assessment_success(self, mock_client_class):
        """Test successful functional assessment retrieval."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Setup mock
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_functional_assessment("UIN", "UIN-TEST-12345")

        self.assertIsNotNone(result)
        self.assertEqual(result["Vision"], 3)
        self.assertEqual(result["Mobility"], 4)
        self.assertEqual(result["Hearing"], 1)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_functional_assessment_missing_params(self, mock_client_class):
        """Test get_functional_assessment validates parameters."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client_class.return_value = MagicMock()
        service = DRService(self.env, data_source_code="dr_test")

        with self.assertRaises(ValidationError):
            service.get_functional_assessment("", "value")

        with self.assertRaises(ValidationError):
            service.get_functional_assessment("type", "")

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_is_pwd_uses_cache(self, mock_client_class):
        """Test is_pwd uses cached disability status."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create cached status
        self.DisabilityStatus.create(
            {
                "partner_id": self.partner.id,
                "has_disability": True,
                "state": "synced",
            }
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.is_pwd(self.partner)

        self.assertTrue(result)
        # Should not call API when cache exists
        mock_client.search_by_id.assert_not_called()

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_is_pwd_fetches_when_no_cache(self, mock_client_class):
        """Test is_pwd fetches from DR when no cache."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # No cached status - use fresh partner
        fresh_partner = self.Partner.create(
            {
                "name": "Fresh Person",
                "is_registrant": True,
            }
        )
        self.IdRecord.create(
            {
                "partner_id": fresh_partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-FRESH-123",
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(has_disability=True)
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.is_pwd(fresh_partner)

        self.assertTrue(result)
        mock_client.search_by_id.assert_called_once()

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_is_pwd_ignores_stale_cache(self, mock_client_class):
        """Test is_pwd fetches from DR when cache is stale."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create stale cached status
        self.DisabilityStatus.create(
            {
                "partner_id": self.partner.id,
                "has_disability": False,
                "state": "stale",  # Stale!
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(has_disability=True)
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.is_pwd(self.partner)

        # Should fetch from API because cache is stale
        self.assertTrue(result)
        mock_client.search_by_id.assert_called_once()

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_sync_disability_data_creates_record(self, mock_client_class):
        """Test sync_disability_data creates new disability status record."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Use fresh partner
        fresh_partner = self.Partner.create(
            {
                "name": "Fresh Sync Person",
                "is_registrant": True,
            }
        )
        self.IdRecord.create(
            {
                "partner_id": fresh_partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-SYNC-123",
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.sync_disability_data(fresh_partner)

        self.assertTrue(result)

        # Check record was created
        status = self.DisabilityStatus.search([("partner_id", "=", fresh_partner.id)])
        self.assertEqual(len(status), 1)
        self.assertTrue(status.has_disability)
        self.assertEqual(status.state, "synced")

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_sync_disability_data_updates_record(self, mock_client_class):
        """Test sync_disability_data updates existing record."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create existing status
        existing = self.DisabilityStatus.create(
            {
                "partner_id": self.partner.id,
                "has_disability": False,  # Old value
                "state": "stale",
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(
            has_disability=True  # New value
        )
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.sync_disability_data(self.partner)

        self.assertTrue(result)

        # Check record was updated
        existing.invalidate_recordset()
        self.assertTrue(existing.has_disability)
        self.assertEqual(existing.state, "synced")

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_sync_disability_data_no_result(self, mock_client_class):
        """Test sync_disability_data handles no DR record found."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Use fresh partner
        fresh_partner = self.Partner.create(
            {
                "name": "No DR Record Person",
                "is_registrant": True,
            }
        )
        self.IdRecord.create(
            {
                "partner_id": fresh_partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-NONE-123",
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = {"message": {"search_response": []}}
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.sync_disability_data(fresh_partner)

        self.assertTrue(result)

        # Check record was created with has_disability=False
        status = self.DisabilityStatus.search([("partner_id", "=", fresh_partner.id)])
        self.assertEqual(len(status), 1)
        self.assertFalse(status.has_disability)
        self.assertEqual(status.state, "synced")

    def test_extract_disability_data_is_pwd_field(self):
        """Test _extract_disability_data handles is_pwd field."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Test with is_pwd field instead of has_disability
        record_data = {
            "is_pwd": True,
            "disability_types": ["Hearing"],
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)
            result = service._extract_disability_data(record_data)

        self.assertTrue(result["has_disability"])

    def test_extract_disability_data_string_types(self):
        """Test _extract_disability_data handles comma-separated types."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        record_data = {
            "has_disability": True,
            "disability_types": "Vision, Hearing, Mobility",
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)
            result = service._extract_disability_data(record_data)

        self.assertEqual(len(result["disability_types"]), 3)
        self.assertIn("Vision", result["disability_types"])
        self.assertIn("Hearing", result["disability_types"])
        self.assertIn("Mobility", result["disability_types"])

    def test_extract_functional_scores_domain_fields(self):
        """Test _extract_functional_scores handles various field formats."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Test with individual domain fields
        record_data = {
            "functional_vision": 3,
            "hearing_score": 1,
            "mobility": 4,
            "Cognition": 2,
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)
            result = service._extract_functional_scores(record_data)

        self.assertEqual(result.get("Vision"), 3)
        self.assertEqual(result.get("Hearing"), 1)
        self.assertEqual(result.get("Mobility"), 4)
        self.assertEqual(result.get("Cognition"), 2)

    def test_extract_functional_scores_json_string(self):
        """Test _extract_functional_scores handles JSON string."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        record_data = {
            "functional_scores": json.dumps({"Vision": 3, "Hearing": 1}),
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)
            result = service._extract_functional_scores(record_data)

        self.assertEqual(result["Vision"], 3)
        self.assertEqual(result["Hearing"], 1)

    def test_get_partner_identifier_priority(self):
        """Test _get_partner_identifier follows priority order."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        # Create partner with multiple IDs
        partner = self.Partner.create(
            {
                "name": "Multi ID Person",
                "is_registrant": True,
            }
        )

        # Add DRN first (lower priority)
        self.IdRecord.create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type_drn.id,
                "value": "DRN-123",
            }
        )

        # Add UIN second (higher priority)
        self.IdRecord.create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-456",
            }
        )

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)
            service.env = self.env
            result = service._get_partner_identifier(partner)

        # Should return UIN_DR_TEST (higher priority vocabulary code)
        self.assertEqual(result[0], "UIN_DR_TEST")
        self.assertEqual(result[1], "UIN-456")
