# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.disability.status model."""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDisabilityStatus(TransactionCase):
    """Tests for DisabilityStatus model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.DisabilityStatus = cls.env["spp.dci.disability.status"]
        cls.Partner = cls.env["res.partner"]

        # Create test partners
        cls.partner1 = cls.Partner.create(
            {
                "name": "Test Person 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.partner2 = cls.Partner.create(
            {
                "name": "Test Person 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_create_disability_status(self):
        """Test creating a disability status record."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "has_disability": True,
                "disability_types": json.dumps(["Vision", "Mobility"]),
                "functional_scores": json.dumps(
                    {
                        "Vision": 3,
                        "Hearing": 1,
                        "Mobility": 4,
                        "Cognition": 1,
                        "SelfCare": 2,
                        "Communication": 1,
                    }
                ),
                "state": "synced",
            }
        )

        self.assertTrue(status.id)
        self.assertEqual(status.partner_id, self.partner1)
        self.assertTrue(status.has_disability)
        self.assertEqual(status.state, "synced")

    def test_partner_unique_constraint(self):
        """Test that only one active disability status per partner is allowed."""
        # Create first status
        self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "has_disability": False,
                "state": "synced",
            }
        )

        # Try to create second active status for same partner
        with self.assertRaises(ValidationError) as cm:
            self.DisabilityStatus.create(
                {
                    "partner_id": self.partner1.id,
                    "has_disability": True,
                    "state": "synced",
                }
            )

        self.assertIn("Only one active disability status", str(cm.exception))

    def test_partner_unique_allows_archived(self):
        """Test that archived records don't trigger uniqueness constraint."""
        # Create and archive first status
        status1 = self.DisabilityStatus.create(
            {
                "partner_id": self.partner2.id,
                "has_disability": False,
                "state": "synced",
            }
        )
        status1.active = False

        # Should be able to create new active status
        status2 = self.DisabilityStatus.create(
            {
                "partner_id": self.partner2.id,
                "has_disability": True,
                "state": "synced",
            }
        )

        self.assertTrue(status2.id)
        self.assertTrue(status2.active)

    def test_assessment_date_not_future(self):
        """Test that assessment date cannot be in the future."""
        future_date = date.today() + timedelta(days=10)

        with self.assertRaises(ValidationError) as cm:
            self.DisabilityStatus.create(
                {
                    "partner_id": self.partner1.id,
                    "assessment_date": future_date,
                    "state": "synced",
                }
            )

        self.assertIn("cannot be in the future", str(cm.exception))

    def test_assessment_date_allows_past(self):
        """Test that past assessment dates are allowed."""
        past_date = date.today() - timedelta(days=30)

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "assessment_date": past_date,
                "state": "synced",
            }
        )

        self.assertEqual(status.assessment_date, past_date)

    def test_assessment_date_allows_today(self):
        """Test that today's date is allowed for assessment."""
        today = date.today()

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "assessment_date": today,
                "state": "synced",
            }
        )

        self.assertEqual(status.assessment_date, today)

    def test_get_disability_types_list(self):
        """Test getting disability types as Python list."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "disability_types": json.dumps(["Vision", "Mobility", "Cognition"]),
                "state": "synced",
            }
        )

        types_list = status.get_disability_types_list()

        self.assertIsInstance(types_list, list)
        self.assertEqual(len(types_list), 3)
        self.assertIn("Vision", types_list)
        self.assertIn("Mobility", types_list)
        self.assertIn("Cognition", types_list)

    def test_get_disability_types_list_empty(self):
        """Test getting disability types when empty."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "disability_types": None,
                "state": "synced",
            }
        )

        types_list = status.get_disability_types_list()

        self.assertIsInstance(types_list, list)
        self.assertEqual(len(types_list), 0)

    def test_get_disability_types_list_invalid_json(self):
        """Test getting disability types with invalid JSON."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )
        # Manually set invalid JSON
        status.disability_types = "not valid json"

        types_list = status.get_disability_types_list()

        self.assertIsInstance(types_list, list)
        self.assertEqual(len(types_list), 0)

    def test_get_functional_scores_dict(self):
        """Test getting functional scores as Python dict."""
        scores = {
            "Vision": 3,
            "Hearing": 1,
            "Mobility": 4,
            "Cognition": 1,
            "SelfCare": 2,
            "Communication": 1,
        }

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "functional_scores": json.dumps(scores),
                "state": "synced",
            }
        )

        scores_dict = status.get_functional_scores_dict()

        self.assertIsInstance(scores_dict, dict)
        self.assertEqual(scores_dict["Vision"], 3)
        self.assertEqual(scores_dict["Mobility"], 4)
        self.assertEqual(scores_dict["Hearing"], 1)

    def test_get_functional_scores_dict_empty(self):
        """Test getting functional scores when empty."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "functional_scores": None,
                "state": "synced",
            }
        )

        scores_dict = status.get_functional_scores_dict()

        self.assertIsInstance(scores_dict, dict)
        self.assertEqual(len(scores_dict), 0)

    def test_get_functional_scores_dict_invalid_json(self):
        """Test getting functional scores with invalid JSON."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )
        # Manually set invalid JSON
        status.functional_scores = "invalid json"

        scores_dict = status.get_functional_scores_dict()

        self.assertIsInstance(scores_dict, dict)
        self.assertEqual(len(scores_dict), 0)

    def test_action_mark_outdated(self):
        """Test marking disability status as stale."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        self.assertEqual(status.state, "synced")

        status.action_mark_outdated()

        self.assertEqual(status.state, "stale")

    def test_state_transitions(self):
        """Test state field values."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        # Test valid state values
        status.state = "stale"
        self.assertEqual(status.state, "stale")

        status.state = "error"
        self.assertEqual(status.state, "error")

        status.state = "synced"
        self.assertEqual(status.state, "synced")

    def test_error_message_on_error_state(self):
        """Test storing error messages."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "error",
                "error_message": "Connection timeout to DR system",
            }
        )

        self.assertEqual(status.state, "error")
        self.assertEqual(status.error_message, "Connection timeout to DR system")

    def test_source_registry_tracking(self):
        """Test source registry is tracked."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "source_registry": "National Disability Registry",
                "state": "synced",
            }
        )

        self.assertEqual(status.source_registry, "National Disability Registry")

    def test_raw_data_storage(self):
        """Test raw DR response can be stored."""
        raw_data = {
            "person_id": "DR-12345",
            "assessment_score": 14,
            "registry_data": {"extra": "info"},
        }

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "raw_data": json.dumps(raw_data),
                "state": "synced",
            }
        )

        stored_data = json.loads(status.raw_data)
        self.assertEqual(stored_data["person_id"], "DR-12345")
        self.assertEqual(stored_data["assessment_score"], 14)

    def test_synced_by_default_user(self):
        """Test synced_by defaults to current user."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        self.assertEqual(status.synced_by, self.env.user)

    def test_last_sync_date_defaults(self):
        """Test last_sync_date is set on creation."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        self.assertIsNotNone(status.last_sync_date)

    def test_record_ordering(self):
        """Test records are ordered by last_sync_date desc."""
        # Create multiple records for different partners
        self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )
        status2 = self.DisabilityStatus.create(
            {
                "partner_id": self.partner2.id,
                "state": "synced",
            }
        )

        # Get all records - most recent should be first
        all_records = self.DisabilityStatus.search([])
        self.assertEqual(all_records[0], status2)

    def test_partner_required_constraint(self):
        """Test that partner_id is required on disability status records.

        Note: The partner_id field has required=True with a database constraint,
        so records cannot exist without a partner. This test verifies that
        constraint is enforced at the ORM level.
        """
        # Attempting to create without partner_id should fail
        # The DB constraint raises IntegrityError, use savepoint to prevent transaction breakage
        from psycopg2 import IntegrityError

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.DisabilityStatus.create(
                {
                    "state": "synced",
                }
            )

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DRService")
    def test_refresh_from_dr_success(self, mock_dr_service_class):
        """Test successful refresh from DR."""
        # Setup mock
        mock_service = MagicMock()
        mock_service.sync_disability_data.return_value = True
        mock_dr_service_class.return_value = mock_service

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "stale",
            }
        )

        result = status.refresh_from_dr()

        self.assertTrue(result)
        mock_service.sync_disability_data.assert_called_once_with(self.partner1)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DRService")
    def test_refresh_from_dr_failure(self, mock_dr_service_class):
        """Test refresh from DR handles failure."""
        # Setup mock to return False
        mock_service = MagicMock()
        mock_service.sync_disability_data.return_value = False
        mock_dr_service_class.return_value = mock_service

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        result = status.refresh_from_dr()

        self.assertFalse(result)
        self.assertEqual(status.state, "error")
        self.assertIn("Failed to retrieve", status.error_message)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DRService")
    def test_refresh_from_dr_exception(self, mock_dr_service_class):
        """Test refresh from DR handles exceptions."""
        # Setup mock to raise exception
        mock_service = MagicMock()
        mock_service.sync_disability_data.side_effect = Exception("Connection error")
        mock_dr_service_class.return_value = mock_service

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        result = status.refresh_from_dr()

        self.assertFalse(result)
        self.assertEqual(status.state, "error")
        self.assertIn("Connection error", status.error_message)

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DRService")
    def test_action_retry_sync(self, mock_dr_service_class):
        """Test retry sync action calls refresh_from_dr."""
        # Setup mock
        mock_service = MagicMock()
        mock_service.sync_disability_data.return_value = True
        mock_dr_service_class.return_value = mock_service

        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "error",
            }
        )

        result = status.action_retry_sync()

        self.assertTrue(result)
        mock_service.sync_disability_data.assert_called_once()

    def test_notes_field(self):
        """Test notes field can store additional information."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "notes": "Manual verification required",
                "state": "synced",
            }
        )

        self.assertEqual(status.notes, "Manual verification required")

    def test_display_name(self):
        """Test record display name uses partner name."""
        status = self.DisabilityStatus.create(
            {
                "partner_id": self.partner1.id,
                "state": "synced",
            }
        )

        # _rec_name is partner_id
        self.assertIn(self.partner1.name, status.display_name)
