# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.duplication.check model."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDuplicationCheck(TransactionCase):
    """Tests for DuplicationCheck model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.DuplicationCheck = cls.env["spp.dci.duplication.check"]
        cls.Partner = cls.env["res.partner"]
        cls.DataSource = cls.env["spp.dci.data.source"]

        # Create test partner
        cls.partner = cls.Partner.create(
            {
                "name": "Test Beneficiary",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create IBR data source (auth_type=none for tests)
        cls.ibr_source = cls.DataSource.create(
            {
                "name": "Test IBR",
                "code": "ibr_test",
                "registry_type": "ibr",
                "base_url": "https://ibr.test.gov/api/v1",
                "auth_type": "none",
                "active": True,
            }
        )

    def test_create_duplication_check(self):
        """Test creating a duplication check record."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-TEST-001",
                "result": "no_match",
                "state": "ready",
            }
        )

        self.assertTrue(check.id)
        self.assertEqual(check.partner_id, self.partner)
        self.assertEqual(check.identifier_type, "UIN")
        self.assertEqual(check.identifier_value, "UIN-TEST-001")
        self.assertEqual(check.result, "no_match")
        self.assertEqual(check.state, "ready")

    def test_identifier_type_required(self):
        """Test identifier_type cannot be empty."""
        with self.assertRaises(ValidationError) as cm:
            self.DuplicationCheck.create(
                {
                    "partner_id": self.partner.id,
                    "identifier_type": "",
                    "identifier_value": "test-value",
                    "result": "no_match",
                }
            )

        self.assertIn("Identifier type cannot be empty", str(cm.exception))

    def test_identifier_type_whitespace(self):
        """Test identifier_type cannot be just whitespace."""
        with self.assertRaises(ValidationError) as cm:
            self.DuplicationCheck.create(
                {
                    "partner_id": self.partner.id,
                    "identifier_type": "   ",
                    "identifier_value": "test-value",
                    "result": "no_match",
                }
            )

        self.assertIn("Identifier type cannot be empty", str(cm.exception))

    def test_identifier_value_required(self):
        """Test identifier_value cannot be empty."""
        with self.assertRaises(ValidationError) as cm:
            self.DuplicationCheck.create(
                {
                    "partner_id": self.partner.id,
                    "identifier_type": "UIN",
                    "identifier_value": "",
                    "result": "no_match",
                }
            )

        self.assertIn("Identifier value cannot be empty", str(cm.exception))

    def test_result_values(self):
        """Test valid result values."""
        # Test no_match
        check1 = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-001",
                "result": "no_match",
            }
        )
        self.assertEqual(check1.result, "no_match")

        # Test possible_match
        check2 = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-002",
                "result": "possible_match",
            }
        )
        self.assertEqual(check2.result, "possible_match")

        # Test confirmed_match
        check3 = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-003",
                "result": "confirmed_match",
            }
        )
        self.assertEqual(check3.result, "confirmed_match")

    def test_state_transitions(self):
        """Test state field values."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-STATE-001",
                "result": "no_match",
                "state": "ready",
            }
        )

        self.assertEqual(check.state, "ready")

        check.state = "checking"
        self.assertEqual(check.state, "checking")

        check.state = "completed"
        self.assertEqual(check.state, "completed")

        check.state = "failed"
        self.assertEqual(check.state, "failed")

    def test_matched_programs_field(self):
        """Test matched_programs field stores program list."""
        programs = "Program A\nProgram B\nProgram C"
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-PROG-001",
                "result": "confirmed_match",
                "matched_programs": programs,
            }
        )

        self.assertEqual(check.matched_programs, programs)
        programs_list = check.matched_programs.split("\n")
        self.assertEqual(len(programs_list), 3)
        self.assertIn("Program A", programs_list)

    def test_raw_response_storage(self):
        """Test raw_response stores API response."""
        raw = '{"status": "success", "matches": []}'
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RAW-001",
                "result": "no_match",
                "raw_response": raw,
            }
        )

        self.assertEqual(check.raw_response, raw)

    def test_error_message_on_failure(self):
        """Test error_message stored on failure."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-ERR-001",
                "result": "no_match",
                "state": "failed",
                "error_message": "Connection timeout to IBR",
            }
        )

        self.assertEqual(check.state, "failed")
        self.assertEqual(check.error_message, "Connection timeout to IBR")

    def test_data_source_link(self):
        """Test linking to data source."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-DS-001",
                "result": "no_match",
                "data_source_id": self.ibr_source.id,
            }
        )

        self.assertEqual(check.data_source_id, self.ibr_source)

    def test_check_date_defaults(self):
        """Test check_date defaults to now."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-DATE-001",
                "result": "no_match",
            }
        )

        self.assertIsNotNone(check.check_date)

    def test_name_get(self):
        """Test custom name_get display."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-NAME-001",
                "result": "no_match",
            }
        )

        display_name = check.name_get()[0][1]

        self.assertIn(self.partner.name, display_name)
        self.assertIn("UIN", display_name)
        self.assertIn("UIN-NAME-001", display_name)

    def test_action_reset_to_draft(self):
        """Test resetting check to ready state."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RESET-001",
                "result": "no_match",
                "state": "failed",
                "error_message": "Some error",
            }
        )

        check.action_reset_to_draft()

        self.assertEqual(check.state, "ready")
        self.assertFalse(check.error_message)

    def test_action_run_check_skips_completed(self):
        """Test action_run_check skips already completed checks."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-SKIP-001",
                "result": "no_match",
                "state": "completed",
            }
        )

        # Should not raise, just skip
        check.action_run_check()

        # State should remain completed
        self.assertEqual(check.state, "completed")

    def test_action_run_check_skips_failed(self):
        """Test action_run_check skips already failed checks."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-SKIP-002",
                "result": "no_match",
                "state": "failed",
            }
        )

        # Should not raise, just skip
        check.action_run_check()

        # State should remain failed
        self.assertEqual(check.state, "failed")

    @patch("odoo.addons.spp_dci_client_ibr.services.IBRService")
    def test_action_run_check_success_no_match(self, mock_ibr_class):
        """Test successful run check with no duplicates found."""
        # Setup mock
        mock_service = MagicMock()
        mock_service.check_duplication.return_value = {
            "is_duplicate": False,
            "matched_programs": [],
            "raw_response": {"status": "success"},
        }
        mock_ibr_class.return_value = mock_service

        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RUN-001",
                "result": "no_match",
                "state": "ready",
                "data_source_id": self.ibr_source.id,
            }
        )

        check.action_run_check()

        self.assertEqual(check.state, "completed")
        self.assertEqual(check.result, "no_match")

    @patch("odoo.addons.spp_dci_client_ibr.services.IBRService")
    def test_action_run_check_success_with_match(self, mock_ibr_class):
        """Test successful run check with duplicates found."""
        # Setup mock
        mock_service = MagicMock()
        mock_service.check_duplication.return_value = {
            "is_duplicate": True,
            "matched_programs": ["Program A", "Program B"],
            "raw_response": {"status": "success", "matches": [{"id": 1}]},
        }
        mock_ibr_class.return_value = mock_service

        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RUN-002",
                "result": "no_match",
                "state": "ready",
                "data_source_id": self.ibr_source.id,
            }
        )

        check.action_run_check()

        self.assertEqual(check.state, "completed")
        self.assertEqual(check.result, "confirmed_match")
        self.assertIn("Program A", check.matched_programs)
        self.assertIn("Program B", check.matched_programs)

    @patch("odoo.addons.spp_dci_client_ibr.services.IBRService")
    def test_action_run_check_failure(self, mock_ibr_class):
        """Test run check handles API failure."""
        # Setup mock to raise exception
        mock_service = MagicMock()
        mock_service.check_duplication.side_effect = Exception("API timeout")
        mock_ibr_class.return_value = mock_service

        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RUN-003",
                "result": "no_match",
                "state": "ready",
                "data_source_id": self.ibr_source.id,
            }
        )

        # action_run_check catches exceptions and sets state to failed
        check.action_run_check()

        self.assertEqual(check.state, "failed")
        self.assertIn("API timeout", check.error_message)

    def test_action_run_check_no_data_source(self):
        """Test run check finds IBR data source automatically."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RUN-004",
                "result": "no_match",
                "state": "ready",
                # No data_source_id set
            }
        )

        with patch("odoo.addons.spp_dci_client_ibr.services.IBRService") as mock_cls:
            mock_service = MagicMock()
            mock_service.check_duplication.return_value = {
                "is_duplicate": False,
                "matched_programs": [],
                "raw_response": {},
            }
            mock_cls.return_value = mock_service

            check.action_run_check()

            # Should have found and linked the IBR data source
            self.assertEqual(check.data_source_id, self.ibr_source)

    def test_action_run_check_no_ibr_source_error(self):
        """Test run check raises error when no IBR source exists."""
        # Archive the IBR source
        self.ibr_source.active = False

        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-RUN-005",
                "result": "no_match",
                "state": "ready",
            }
        )

        with self.assertRaises(UserError) as cm:
            check.action_run_check()

        self.assertIn("No active IBR data source", str(cm.exception))

        # Restore IBR source
        self.ibr_source.active = True

    def test_ordering_by_check_date(self):
        """Test records ordered by check_date descending."""
        check1 = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-ORD-001",
                "result": "no_match",
            }
        )

        check2 = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-ORD-002",
                "result": "no_match",
            }
        )

        # Most recent should be first
        all_checks = self.DuplicationCheck.search([])
        self.assertEqual(all_checks[0], check2)

    def test_notes_field(self):
        """Test notes field stores additional info."""
        check = self.DuplicationCheck.create(
            {
                "partner_id": self.partner.id,
                "identifier_type": "UIN",
                "identifier_value": "UIN-NOTE-001",
                "result": "possible_match",
                "notes": "Requires manual review - potential data quality issue",
            }
        )

        self.assertEqual(check.notes, "Requires manual review - potential data quality issue")
