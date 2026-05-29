# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.sr.record model."""

import json
from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSRRecord(TransactionCase):
    """Test cases for SR Record model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRRecord = cls.env["spp.dci.sr.record"]
        cls.Partner = cls.env["res.partner"]

        # Create test partner
        cls.test_partner = cls.Partner.create(
            {
                "name": "Test Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_create_sr_record(self):
        """Test creating SR record."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT123",
                "source_registry": "SR_001",
                "state": "synced",
            }
        )
        self.assertEqual(record.partner_id, self.test_partner)
        self.assertEqual(record.external_id, "EXT123")
        self.assertEqual(record.source_registry, "SR_001")
        self.assertEqual(record.state, "synced")
        self.assertTrue(record.active)

    def test_create_sr_record_with_demographics(self):
        """Test creating SR record with demographic data."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT124",
                "source_registry": "SR_001",
                "sr_name": "John Doe",
                "sr_birth_date": "1990-05-15",
                "sr_gender": "male",
                "sr_address": "123 Main St, City",
                "state": "synced",
            }
        )
        self.assertEqual(record.sr_name, "John Doe")
        self.assertEqual(record.sr_gender, "male")
        self.assertEqual(record.sr_address, "123 Main St, City")

    def test_create_sr_record_with_household(self):
        """Test creating SR record with household data."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT125",
                "source_registry": "SR_001",
                "household_id": "HH_001",
                "household_size": 5,
                "is_head_of_household": True,
                "state": "synced",
            }
        )
        self.assertEqual(record.household_id, "HH_001")
        self.assertEqual(record.household_size, 5)
        self.assertTrue(record.is_head_of_household)

    def test_enrolled_programs_json(self):
        """Test enrolled_programs JSON field."""
        programs = ["Cash Transfer", "Food Assistance", "Education Grant"]
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT126",
                "source_registry": "SR_001",
                "enrolled_programs": json.dumps(programs),
                "state": "synced",
            }
        )
        programs_list = record.get_enrolled_programs()
        self.assertEqual(programs_list, programs)
        self.assertEqual(record.program_count, 3)

    def test_get_enrolled_programs_empty(self):
        """Test get_enrolled_programs with empty data."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT127",
                "source_registry": "SR_001",
                "state": "synced",
            }
        )
        programs_list = record.get_enrolled_programs()
        self.assertEqual(programs_list, [])

    def test_get_enrolled_programs_invalid_json(self):
        """Test get_enrolled_programs with invalid JSON."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT128",
                "source_registry": "SR_001",
                "enrolled_programs": "not valid json",
                "state": "synced",
            }
        )
        programs_list = record.get_enrolled_programs()
        self.assertEqual(programs_list, [])

    def test_is_enrolled_in_program(self):
        """Test is_enrolled_in method."""
        programs = ["Cash Transfer", "Food Assistance"]
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT129",
                "source_registry": "SR_001",
                "enrolled_programs": json.dumps(programs),
                "state": "synced",
            }
        )
        self.assertTrue(record.is_enrolled_in("Cash Transfer"))
        self.assertFalse(record.is_enrolled_in("Health Insurance"))

    def test_is_enrolled_in_program_dict_format(self):
        """Test is_enrolled_in with dict program format."""
        programs = [
            {"id": "prog_001", "name": "Cash Transfer"},
            {"id": "prog_002", "name": "Food Assistance"},
        ]
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT129b",
                "source_registry": "SR_001",
                "enrolled_programs": json.dumps(programs),
                "state": "synced",
            }
        )
        self.assertTrue(record.is_enrolled_in("Cash Transfer"))
        self.assertTrue(record.is_enrolled_in("prog_001"))
        self.assertFalse(record.is_enrolled_in("prog_999"))

    def test_state_transitions(self):
        """Test state transitions."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT130",
                "source_registry": "SR_001",
                "state": "synced",
            }
        )
        self.assertEqual(record.state, "synced")

        record.action_mark_stale()
        self.assertEqual(record.state, "stale")

    def test_action_retry_sync(self):
        """Test retry sync action."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT131",
                "source_registry": "SR_001",
                "state": "error",
                "error_message": "Previous sync failed",
            }
        )
        self.assertEqual(record.state, "error")

        with patch.object(type(record), "refresh_from_sr") as mock_refresh:
            record.action_retry_sync()
            mock_refresh.assert_called_once()

    def test_compute_program_count(self):
        """Test program_count computed field."""
        programs = ["Program A", "Program B", "Program C"]
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT132",
                "source_registry": "SR_001",
                "enrolled_programs": json.dumps(programs),
                "state": "synced",
            }
        )
        self.assertEqual(record.program_count, 3)

        # Update with fewer programs
        record.enrolled_programs = json.dumps(["Program A"])
        self.assertEqual(record.program_count, 1)

    def test_raw_data_storage(self):
        """Test raw_data JSON storage."""
        raw_data = {
            "id": "EXT133",
            "name": "Test Person",
            "attributes": {"key1": "value1"},
        }
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT133",
                "source_registry": "SR_001",
                "raw_data": json.dumps(raw_data),
                "state": "synced",
            }
        )
        stored_data = json.loads(record.raw_data)
        self.assertEqual(stored_data["id"], "EXT133")
        self.assertEqual(stored_data["attributes"]["key1"], "value1")

    def test_synced_by_tracking(self):
        """Test synced_by field tracking."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT134",
                "source_registry": "SR_001",
                "state": "synced",
                "synced_by": self.env.user.id,
                "last_sync_date": fields.Datetime.now(),
            }
        )
        self.assertEqual(record.synced_by, self.env.user)
        self.assertIsNotNone(record.last_sync_date)

    def test_toggle_active(self):
        """Test archiving/unarchiving record."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT135",
                "source_registry": "SR_001",
                "state": "synced",
            }
        )
        self.assertTrue(record.active)

        record.toggle_active()
        self.assertFalse(record.active)
