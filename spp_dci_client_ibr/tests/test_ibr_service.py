# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for IBRService."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIBRService(TransactionCase):
    """Tests for IBRService."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Partner = cls.env["res.partner"]
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.IdRecord = cls.env["spp.registry.id"]

        # Get or create ID type vocabulary
        id_type_vocab = cls.Vocabulary.search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.Vocabulary.create(
                {
                    "name": "ID Types",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        # Create test ID type codes (is_local=True for test data)
        cls.id_type_uin = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "UIN_IBR_TEST",
                "display": "Universal Identification Number",
                "target_type": "individual",
                "is_local": True,
            }
        )
        cls.id_type_brn = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "BRN_TEST",
                "display": "Birth Registration Number",
                "target_type": "individual",
                "is_local": True,
            }
        )

        # Create test partner with identifiers
        cls.partner = cls.Partner.create(
            {
                "name": "Test IBR Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create ID records using spp.registry.id model
        cls.id_record = cls.IdRecord.create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-IBR-TEST-12345",
            }
        )

        # Create IBR data source (auth_type=none for tests)
        cls.data_source = cls.DataSource.create(
            {
                "name": "Test IBR Registry",
                "code": "ibr_test",
                "registry_type": "ibr",
                "base_url": "https://ibr.test.gov/api/v1",
                "auth_type": "none",
                "active": True,
            }
        )

    def _create_mock_search_response(
        self,
        has_matches=True,
        programs=None,
        name="John Doe",
    ):
        """Helper to create mock IBR search response."""
        if programs is None:
            programs = ["Social Protection Program", "Food Assistance"]

        if not has_matches:
            return {"message": {"search_response": []}}

        return {
            "message": {
                "search_response": [
                    {
                        "reference_id": "ref-001",
                        "status": "succ",
                        "data": [
                            {
                                "given_name": name.split()[0] if name else "",
                                "family_name": name.split()[-1] if name else "",
                                "identifiers": [{"type": "UIN", "value": "UIN-IBR-TEST-12345"}],
                                "programs": [{"name": p} for p in programs],
                            }
                        ],
                    }
                ]
            }
        }

    def test_service_init(self):
        """Test IBRService initialization."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        with patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            service = IBRService(self.data_source, self.env)

            self.assertEqual(service.data_source, self.data_source)
            self.assertEqual(service.env, self.env)
            mock_cls.assert_called_once_with(self.data_source, self.env)

    def test_service_init_no_data_source(self):
        """Test IBRService raises error without data source."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        with self.assertRaises(ValueError):
            IBRService(None, self.env)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_check_duplication_no_match(self, mock_client_class):
        """Test check_duplication with no duplicates found."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(has_matches=False)
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.check_duplication(self.partner)

        self.assertFalse(result["is_duplicate"])
        self.assertEqual(len(result["matched_programs"]), 0)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_check_duplication_with_match(self, mock_client_class):
        """Test check_duplication with duplicates found."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(
            has_matches=True,
            programs=["Program A", "Program B"],
        )
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.check_duplication(self.partner)

        self.assertTrue(result["is_duplicate"])
        self.assertIn("Program A", result["matched_programs"])
        self.assertIn("Program B", result["matched_programs"])

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_check_duplication_no_partner(self, mock_client_class):
        """Test check_duplication raises error without partner."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client_class.return_value = MagicMock()
        service = IBRService(self.data_source, self.env)

        with self.assertRaises(ValueError):
            service.check_duplication(None)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_check_duplication_no_identifiers(self, mock_client_class):
        """Test check_duplication raises error for partner without IDs."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        # Create partner without identifiers
        partner_no_id = self.Partner.create(
            {
                "name": "No ID Person",
                "is_registrant": True,
            }
        )

        mock_client_class.return_value = MagicMock()
        service = IBRService(self.data_source, self.env)

        with self.assertRaises(UserError) as cm:
            service.check_duplication(partner_no_id)

        self.assertIn("no identifiers configured", str(cm.exception))

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_search_beneficiary_success(self, mock_client_class):
        """Test successful beneficiary search."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(name="Jane Smith")
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.search_beneficiary("UIN", "UIN-TEST-001")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Jane Smith")

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_search_beneficiary_no_results(self, mock_client_class):
        """Test beneficiary search with no results."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(has_matches=False)
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.search_beneficiary("UIN", "NON-EXISTENT")

        self.assertEqual(len(result), 0)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_search_beneficiary_api_error(self, mock_client_class):
        """Test beneficiary search handles API errors."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)

        with self.assertRaises(UserError) as cm:
            service.search_beneficiary("UIN", "UIN-TEST-001")

        self.assertIn("Failed to search", str(cm.exception))

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_get_enrollment_status_enrolled(self, mock_client_class):
        """Test get_enrollment_status when beneficiary is enrolled."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(programs=["Program X", "Program Y"])
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.get_enrollment_status("UIN", "UIN-TEST-001")

        self.assertTrue(result["enrolled"])
        self.assertIn("Program X", result["programs"])
        self.assertIn("Program Y", result["programs"])
        self.assertIsNotNone(result["beneficiary_info"])

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_get_enrollment_status_not_enrolled(self, mock_client_class):
        """Test get_enrollment_status when beneficiary is not found."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        mock_client = MagicMock()
        mock_client.search_by_id.return_value = self._create_mock_search_response(has_matches=False)
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.get_enrollment_status("UIN", "NON-EXISTENT")

        self.assertFalse(result["enrolled"])
        self.assertEqual(len(result["programs"]), 0)
        self.assertIsNone(result["beneficiary_info"])

    def test_duplication_result_class(self):
        """Test DuplicationResult helper class."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import DuplicationResult

        result = DuplicationResult(
            is_duplicate=True,
            matched_programs=["Program A"],
            raw_response={"data": "test"},
        )

        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.matched_programs, ["Program A"])
        self.assertEqual(result.raw_response, {"data": "test"})

        # Test to_dict
        result_dict = result.to_dict()
        self.assertTrue(result_dict["is_duplicate"])
        self.assertIn("Program A", result_dict["matched_programs"])

    def test_duplication_result_defaults(self):
        """Test DuplicationResult default values."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import DuplicationResult

        result = DuplicationResult()

        self.assertFalse(result.is_duplicate)
        self.assertEqual(result.matched_programs, [])
        self.assertEqual(result.raw_response, {})

    def test_beneficiary_info_class(self):
        """Test BeneficiaryInfo helper class."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import BeneficiaryInfo

        info = BeneficiaryInfo(
            identifier_type="UIN",
            identifier_value="UIN-001",
            name="John Doe",
            programs=["Program A"],
            metadata={"extra": "data"},
        )

        self.assertEqual(info.identifier_type, "UIN")
        self.assertEqual(info.identifier_value, "UIN-001")
        self.assertEqual(info.name, "John Doe")
        self.assertEqual(info.programs, ["Program A"])
        self.assertEqual(info.metadata, {"extra": "data"})

        # Test to_dict
        info_dict = info.to_dict()
        self.assertEqual(info_dict["identifier_type"], "UIN")
        self.assertEqual(info_dict["name"], "John Doe")

    def test_beneficiary_info_defaults(self):
        """Test BeneficiaryInfo default values."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import BeneficiaryInfo

        info = BeneficiaryInfo(
            identifier_type="UIN",
            identifier_value="UIN-001",
        )

        self.assertIsNone(info.name)
        self.assertEqual(info.programs, [])
        self.assertEqual(info.metadata, {})

    def test_parse_search_response_empty(self):
        """Test _parse_search_response with empty response."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._parse_search_response({})

        self.assertEqual(result, [])

    def test_parse_search_response_invalid(self):
        """Test _parse_search_response with invalid structure."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._parse_search_response({"invalid": "data"})

        self.assertEqual(result, [])

    def test_extract_name_full_name(self):
        """Test _extract_name with full_name field."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {"full_name": "John Doe"}

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_name(record)

        self.assertEqual(result, "John Doe")

    def test_extract_name_given_family(self):
        """Test _extract_name with given_name and family_name."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {"given_name": "John", "family_name": "Doe"}

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_name(record)

        self.assertEqual(result, "John Doe")

    def test_extract_name_none(self):
        """Test _extract_name with no name fields."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {"other_field": "value"}

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_name(record)

        self.assertIsNone(result)

    def test_extract_identifiers_list(self):
        """Test _extract_identifiers with identifier list."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {
            "identifiers": [
                {"type": "UIN", "value": "UIN-001"},
                {"type": "BRN", "value": "BRN-001"},
            ]
        }

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_identifiers(record)

        self.assertEqual(len(result), 2)

    def test_extract_identifiers_common_fields(self):
        """Test _extract_identifiers with common ID fields."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {
            "uin": "UIN-123",
            "brn": "BRN-456",
        }

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_identifiers(record)

        self.assertEqual(len(result), 2)
        types = [id_info["type"] for id_info in result]
        self.assertIn("UIN", types)
        self.assertIn("BRN", types)

    def test_extract_programs_list(self):
        """Test _extract_programs with program list."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {
            "programs": [
                {"name": "Program A"},
                {"name": "Program B"},
                "Program C",  # String format
            ]
        }

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_programs(record)

        self.assertEqual(len(result), 3)
        self.assertIn("Program A", result)
        self.assertIn("Program B", result)
        self.assertIn("Program C", result)

    def test_extract_programs_enrollments(self):
        """Test _extract_programs with enrollments field."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        record = {
            "enrollments": [
                {"program_name": "Program X"},
                {"program_id": "PROG-Y"},
            ]
        }

        with patch.object(IBRService, "__init__", lambda x, y, z: None):
            service = IBRService.__new__(IBRService)
            result = service._extract_programs(record)

        self.assertEqual(len(result), 2)
        self.assertIn("Program X", result)
        self.assertIn("PROG-Y", result)

    @patch("odoo.addons.spp_dci_client_ibr.services.ibr_service.DCIClient")
    def test_check_duplication_continues_on_partial_error(self, mock_client_class):
        """Test check_duplication continues checking other IDs on error."""
        from odoo.addons.spp_dci_client_ibr.services.ibr_service import IBRService

        # Create partner with multiple IDs
        partner = self.Partner.create(
            {
                "name": "Multi ID Person",
                "is_registrant": True,
            }
        )
        self.IdRecord.create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type_uin.id,
                "value": "UIN-MULTI-001",
            }
        )
        self.IdRecord.create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type_brn.id,
                "value": "BRN-MULTI-001",
            }
        )

        # Mock: first call fails, second succeeds
        mock_client = MagicMock()
        mock_client.search_by_id.side_effect = [
            Exception("First ID failed"),
            self._create_mock_search_response(programs=["Found Program"]),
        ]
        mock_client_class.return_value = mock_client

        service = IBRService(self.data_source, self.env)
        result = service.check_duplication(partner)

        # Should still find the match from second ID
        self.assertTrue(result["is_duplicate"])
        self.assertIn("Found Program", result["matched_programs"])
