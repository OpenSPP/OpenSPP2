# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Additional coverage for spp.dci.sr.record model.

Targets the branches in refresh_from_sr(), _update_from_sr_response(),
and action_retry_sync() that are not reached by test_sr_record.py.
"""

import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSRRecordRefresh(TransactionCase):
    """Cover refresh_from_sr() branches not reached by existing tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRRecord = cls.env["spp.dci.sr.record"]
        cls.Partner = cls.env["res.partner"]
        cls.test_partner = cls.Partner.create(
            {
                "name": "Refresh Test Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _create_record(self, **kwargs):
        vals = {
            "partner_id": self.test_partner.id,
            "external_id": "EXT-REFRESH",
            "source_registry": "sr.test",
            "state": "error",
        }
        vals.update(kwargs)
        return self.SRRecord.create(vals)

    # --- refresh_from_sr: no active data source ---

    def test_refresh_no_data_source_returns_false(self):
        """When no active SR data source exists, refresh_from_sr returns False."""
        record = self._create_record(identifier_type="UIN", identifier_value="NO-DS-001")

        # Ensure no SR data sources are active for this test.
        active_sources = self.env["spp.dci.data.source"].search(
            [("registry_type", "=", "sr"), ("state", "=", "active")]
        )
        active_sources.write({"state": "inactive"})

        try:
            result = record.refresh_from_sr()
        finally:
            active_sources.write({"state": "active"})

        self.assertFalse(result)
        record.invalidate_recordset()
        self.assertEqual(record.state, "error")

    # --- refresh_from_sr: person not found in SR ---

    def test_refresh_person_not_found_sets_error(self):
        """When search_person returns None, refresh marks the record as error."""
        data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "SR Refresh DS",
                "code": "sr_refresh_ds",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.refresh",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )
        record = self._create_record(identifier_type="UIN", identifier_value="NOTFOUND-001")

        with patch("odoo.addons.spp_dci_client_sr.services.SRService") as MockService:
            instance = MockService.return_value
            instance.search_person.return_value = None

            result = record.refresh_from_sr()

        self.assertFalse(result)
        record.invalidate_recordset()
        self.assertEqual(record.state, "error")
        self.assertIn("not found", record.error_message)

        data_source.unlink()

    # --- refresh_from_sr: search_person raises an exception ---

    def test_refresh_exception_sets_error(self):
        """When SRService raises, refresh_from_sr catches and returns False."""
        data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "SR Refresh Exception DS",
                "code": "sr_refresh_exc_ds",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.refresh.exc",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )
        record = self._create_record(identifier_type="UIN", identifier_value="EXC-001")

        with patch("odoo.addons.spp_dci_client_sr.services.SRService") as MockService:
            MockService.side_effect = RuntimeError("connection refused")

            result = record.refresh_from_sr()

        self.assertFalse(result)
        record.invalidate_recordset()
        self.assertEqual(record.state, "error")
        self.assertIn("connection refused", record.error_message)

        data_source.unlink()

    # --- refresh_from_sr: successful refresh ---

    def test_refresh_success_updates_record(self):
        """When search_person returns data, _update_from_sr_response is called."""
        data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "SR Refresh Success DS",
                "code": "sr_refresh_ok_ds",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.refresh.ok",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )
        record = self._create_record(identifier_type="UIN", identifier_value="OK-001")

        person_data = {"id": "EXT-OK", "name": "Refreshed Name", "gender": "female"}

        with patch("odoo.addons.spp_dci_client_sr.services.SRService") as MockService:
            instance = MockService.return_value
            instance.search_person.return_value = person_data

            result = record.refresh_from_sr()

        self.assertTrue(result)
        record.invalidate_recordset()
        self.assertEqual(record.state, "synced")
        self.assertEqual(record.sr_name, "Refreshed Name")

        data_source.unlink()

    # --- refresh_from_sr: uses external_id when identifier_value is falsy ---

    def test_refresh_uses_external_id_as_fallback(self):
        """When identifier_value is absent, external_id is passed to search_person."""
        data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "SR Refresh Fallback DS",
                "code": "sr_refresh_fb_ds",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.refresh.fb",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )
        # No identifier_value, no identifier_type - both fields absent.
        record = self._create_record(external_id="EXT-FALLBACK")

        with patch("odoo.addons.spp_dci_client_sr.services.SRService") as MockService:
            instance = MockService.return_value
            instance.search_person.return_value = None

            record.refresh_from_sr()
            # search_person must have been called with "UIN" and the external_id.
            call_args = instance.search_person.call_args
            self.assertEqual(call_args[0][0], "UIN")
            self.assertEqual(call_args[0][1], "EXT-FALLBACK")

        data_source.unlink()


@tagged("post_install", "-at_install")
class TestSRRecordUpdateFromSR(TransactionCase):
    """Cover _update_from_sr_response() branches not reached by existing tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRRecord = cls.env["spp.dci.sr.record"]
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Update SR Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _create_record(self):
        return self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT-UPDATE",
                "source_registry": "sr.update",
                "state": "error",
            }
        )

    def test_update_address_as_dict_serialised(self):
        """When data['address'] is a dict it must be JSON-serialised into sr_address."""
        record = self._create_record()
        address_dict = {"street": "123 Main St", "city": "Testville"}
        record._update_from_sr_response({"address": address_dict})
        record.invalidate_recordset()
        stored = json.loads(record.sr_address)
        self.assertEqual(stored["city"], "Testville")

    def test_update_address_as_string(self):
        """When data['address'] is a plain string it is stored as-is."""
        record = self._create_record()
        record._update_from_sr_response({"address": "456 Elm Street"})
        record.invalidate_recordset()
        self.assertEqual(record.sr_address, "456 Elm Street")

    def test_update_household_fields(self):
        """household_id, household_size and is_head_of_household are all mapped."""
        record = self._create_record()
        record._update_from_sr_response(
            {
                "household_id": "HH-999",
                "household_size": 7,
                "is_head_of_household": True,
            }
        )
        record.invalidate_recordset()
        self.assertEqual(record.household_id, "HH-999")
        self.assertEqual(record.household_size, 7)
        self.assertTrue(record.is_head_of_household)

    def test_update_clears_error_and_sets_synced(self):
        """State is always reset to 'synced' and error_message is cleared."""
        record = self._create_record()
        self.assertEqual(record.state, "error")
        record._update_from_sr_response({"name": "Clean Slate"})
        record.invalidate_recordset()
        self.assertEqual(record.state, "synced")
        self.assertFalse(record.error_message)

    def test_update_enrolled_programs_serialised(self):
        """enrolled_programs list is JSON-serialised."""
        record = self._create_record()
        programs = ["Cash Transfer", "Education"]
        record._update_from_sr_response({"enrolled_programs": programs})
        record.invalidate_recordset()
        self.assertEqual(json.loads(record.enrolled_programs), programs)


@tagged("post_install", "-at_install")
class TestSRRecordRetrySync(TransactionCase):
    """Cover action_retry_sync() filtering behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRRecord = cls.env["spp.dci.sr.record"]
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Retry Sync Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_action_retry_sync_skips_non_error_records(self):
        """action_retry_sync only calls refresh_from_sr on error-state records."""
        synced_record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT-SYNCED",
                "source_registry": "sr.test",
                "state": "synced",
            }
        )
        error_record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT-ERROR",
                "source_registry": "sr.test2",
                "state": "error",
            }
        )

        refreshed = []

        def fake_refresh(self_rec):
            refreshed.append(self_rec.id)

        with patch.object(type(synced_record), "refresh_from_sr", fake_refresh):
            (synced_record | error_record).action_retry_sync()

        # Only the error record should have triggered refresh.
        self.assertIn(error_record.id, refreshed)
        self.assertNotIn(synced_record.id, refreshed)

    def test_action_retry_sync_on_stale_is_skipped(self):
        """Stale records are also skipped — only 'error' triggers refresh."""
        stale_record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT-STALE",
                "source_registry": "sr.stale",
                "state": "stale",
            }
        )

        refreshed = []

        def fake_refresh(self_rec):
            refreshed.append(self_rec.id)

        with patch.object(type(stale_record), "refresh_from_sr", fake_refresh):
            stale_record.action_retry_sync()

        self.assertNotIn(stale_record.id, refreshed)

    def test_compute_program_count_non_list_json(self):
        """When enrolled_programs contains a non-list JSON value, count is 0."""
        record = self.SRRecord.create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT-NONLIST",
                "source_registry": "sr.nonlist",
                "enrolled_programs": json.dumps({"key": "value"}),
                "state": "synced",
            }
        )
        self.assertEqual(record.program_count, 0)
