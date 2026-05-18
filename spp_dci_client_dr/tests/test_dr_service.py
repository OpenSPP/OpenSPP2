# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DRService."""

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
        disability_status="Approved",
        impairment_types=None,
        last_updated="2024-11-15",
        source_registry="National DR",
    ):
        """Build a DCI v1.0.0 spec-envelope mock response."""
        if impairment_types is None:
            impairment_types = ["Vision", "Mobility"]
        record = {
            "disability_status": disability_status,
            "disability_details": [{"impairment_type": t} for t in impairment_types],
            "last_updated": last_updated,
            "source_registry": source_registry,
        }
        return {
            "message": {
                "search_response": [
                    {
                        "reference_id": "ref-001",
                        "status": "succ",
                        "data": {
                            "version": "1.0.0",
                            "reg_type": "DR",
                            "reg_record_type": "PERSON",
                            "reg_records": [record],
                        },
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
        """Test successful disability status retrieval with spec envelope."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertTrue(result["has_disability"])
        self.assertIn("Vision", result["disability_types"])
        self.assertIn("Mobility", result["disability_types"])
        self.assertEqual(result["functional_scores"], {})

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

        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = Exception("API connection failed")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")

        with self.assertRaises(UserError) as cm:
            service.get_disability_status(self.partner)

        self.assertIn("Failed to get disability status", str(cm.exception))

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_functional_assessment_success(self, mock_client_class):
        """Test functional assessment returns empty dict (no numeric scores in spec)."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response()
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_functional_assessment("UIN", "UIN-TEST-12345")

        self.assertIsNotNone(result)
        self.assertEqual(result, {})

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
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Approved")
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
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Approved")
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
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Approved")
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
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Approved")
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

    # --- additional spec-form coverage ---

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_spec_rejected(self, mock_client_class):
        """Test get_disability_status with rejected status returns has_disability=False."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Rejected")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertFalse(result["has_disability"])

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_spec_unknown_status_warns(self, mock_client_class):
        """Test get_disability_status with unknown status emits WARNING and returns True (has impairments)."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Pending")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING") as cm:
            result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertTrue(result["has_disability"])
        self.assertTrue(any("Pending" in line for line in cm.output))

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_extracts_impairment_types(self, mock_client_class):
        """Test that impairment_type values are extracted into disability_types."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(
            impairment_types=["Physical and movement related functions"]
        )
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertIn("Physical and movement related functions", result["disability_types"])

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_sync_disability_data_creates_record_rejected(self, mock_client_class):
        """Test sync with rejected status creates record with has_disability=False."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        rejected_partner = self.Partner.create(
            {
                "name": "Rejected Person",
                "is_registrant": True,
            }
        )
        self.IdRecord.create(
            {
                "partner_id": rejected_partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-REJECTED-123",
            }
        )

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Rejected")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.sync_disability_data(rejected_partner)

        self.assertTrue(result)

        status = self.DisabilityStatus.search([("partner_id", "=", rejected_partner.id)])
        self.assertEqual(len(status), 1)
        self.assertFalse(status.has_disability)
        self.assertEqual(status.state, "synced")

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_functional_assessment_spec_envelope(self, mock_client_class):
        """Test get_functional_assessment with spec envelope returns empty scores without raising."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(disability_status="Approved")
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_functional_assessment("UIN", "UIN-TEST-12345")

        # Spec has no numeric scores: must return empty dict, not raise
        self.assertIsNotNone(result)
        self.assertEqual(result, {})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_empty_data(self, mock_client_class):
        """Test get_disability_status returns None when data is empty envelope."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = {
            "message": {
                "search_response": [
                    {
                        "reference_id": "ref-001",
                        "status": "succ",
                        "data": {
                            "version": "1.0.0",
                            "reg_record_type": "PERSON",
                            "reg_records": [],
                        },
                    }
                ]
            }
        }
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNone(result)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_missing_data_key(self, mock_client_class):
        """Test get_disability_status returns None when data key is absent."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = {
            "message": {
                "search_response": [
                    {
                        "reference_id": "ref-001",
                        "status": "succ",
                    }
                ]
            }
        }
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNone(result)

    def test_extract_disability_data_delegates_to_module(self):
        """Test _extract_disability_data thin-delegates to dr_parsing module function."""
        from odoo.addons.spp_dci_client_dr.services.dr_parsing import extract_disability_data
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        record = {
            "disability_status": "Approved",
            "disability_details": [{"impairment_type": "Vision"}],
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)

        service_result = service._extract_disability_data(record)
        module_result = extract_disability_data(record)

        self.assertEqual(service_result, module_result)

    def test_extract_functional_scores_delegates_to_module(self):
        """Test _extract_functional_scores thin-delegates to dr_parsing module function."""
        from odoo.addons.spp_dci_client_dr.services.dr_parsing import extract_functional_scores
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        record = {
            "disability_status": "Approved",
            "disability_details": [{"impairment_type": "Vision"}],
        }

        with patch.object(DRService, "__init__", lambda x, y, z: None):
            service = DRService.__new__(DRService)

        self.assertEqual(service._extract_functional_scores(record), extract_functional_scores(record))
        self.assertEqual(service._extract_functional_scores(record), {})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_spec_envelope_approved(self, mock_client_class):
        """Test get_disability_status with DCI v1.0.0 spec envelope, approved status."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(
            disability_status="Approved",
            impairment_types=["Physical and movement related functions"],
        )
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertTrue(result["has_disability"])

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_spec_envelope_rejected(self, mock_client_class):
        """Test get_disability_status with DCI v1.0.0 spec envelope, rejected status."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(
            disability_status="Rejected",
            impairment_types=["Physical"],
        )
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertFalse(result["has_disability"])

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_get_disability_status_spec_envelope_impairments(self, mock_client_class):
        """Test that impairment_type values are extracted into disability_types."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_response(
            disability_status="Approved",
            impairment_types=["Physical and movement related functions"],
        )
        mock_client_class.return_value = mock_client

        service = DRService(self.env, data_source_code="dr_test")
        result = service.get_disability_status(self.partner)

        self.assertIsNotNone(result)
        self.assertIn("Physical and movement related functions", result["disability_types"])
