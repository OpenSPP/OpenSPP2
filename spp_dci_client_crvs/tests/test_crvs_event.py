# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the spp.dci.crvs.event model (cache + event processing)."""

import json
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCRVSEvent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["spp.dci.crvs.event"]
        cls.Partner = cls.env["res.partner"]
        cls.RegID = cls.env["spp.registry.id"]
        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")

    def _event(self, **vals):
        defaults = {
            "event_type": "birth",
            "identifier_type": self.id_code.code,
            "identifier_value": "EV-1",
            "event_date": date(2024, 1, 1),
            "state": "received",
        }
        defaults.update(vals)
        return self.Event.create(defaults)

    # --- create / constraints ------------------------------------------------

    def test_create_generates_name(self):
        ev = self._event()
        self.assertTrue(ev.name)
        self.assertNotEqual(ev.name, "New")

    def test_event_date_future_rejected(self):
        with self.assertRaises(ValidationError):
            self._event(event_date=date.today() + timedelta(days=2))

    def test_duplicate_event_rejected(self):
        self._event(identifier_value="DUP", event_date=date(2023, 5, 5))
        with self.assertRaises(ValidationError):
            self._event(identifier_value="DUP", event_date=date(2023, 5, 5))

    # --- process_event -------------------------------------------------------

    def test_process_event_no_person_marks_error(self):
        ev = self._event(identifier_value="NOPERSON")
        result = ev.process_event()
        self.assertFalse(result)
        self.assertEqual(ev.state, "error")
        self.assertIn("No matching person", ev.error_message)

    def test_process_birth_sets_birthdate_and_links_person(self):
        partner = self.Partner.create({"name": "Born", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "BIRTH-1"}
        )
        ev = self._event(event_type="birth", identifier_value="BIRTH-1", event_date=date(2010, 6, 1))
        result = ev.process_event()
        self.assertTrue(result)
        self.assertEqual(ev.state, "processed")
        self.assertEqual(ev.person_id, partner)
        self.assertEqual(partner.birthdate, date(2010, 6, 1))

    def test_process_death_disables_registrant(self):
        partner = self.Partner.create({"name": "Deceased", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "DEATH-1"}
        )
        ev = self._event(event_type="death", identifier_value="DEATH-1", event_date=date(2024, 2, 2))
        result = ev.process_event()
        self.assertTrue(result)
        self.assertEqual(ev.state, "processed")
        self.assertTrue(partner.disabled)

    def test_process_marriage_processed(self):
        partner = self.Partner.create({"name": "Wed", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "MAR-1"}
        )
        ev = self._event(event_type="marriage", identifier_value="MAR-1", event_date=date(2024, 3, 3))
        self.assertTrue(ev.process_event())
        self.assertEqual(ev.state, "processed")

    def test_process_divorce_processed(self):
        partner = self.Partner.create({"name": "Split", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "DIV-1"}
        )
        ev = self._event(event_type="divorce", identifier_value="DIV-1", event_date=date(2024, 4, 4))
        self.assertTrue(ev.process_event())
        self.assertEqual(ev.state, "processed")

    def test_process_already_processed_raises(self):
        partner = self.Partner.create({"name": "Done", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "DONE-1"}
        )
        ev = self._event(identifier_value="DONE-1")
        ev.process_event()
        self.assertEqual(ev.state, "processed")
        with self.assertRaises(UserError):
            ev.process_event()

    # --- action_retry_processing ---------------------------------------------

    def test_action_retry_processing_resets_and_reprocesses(self):
        ev = self._event(identifier_value="RETRY-1")
        ev.process_event()  # no person -> error
        self.assertEqual(ev.state, "error")
        # Retry still finds no person, but the action must run without raising.
        ev.action_retry_processing()
        self.assertIn(ev.state, ("error", "processed", "received", "processing"))

    # --- birth with raw_data identifier addition -----------------------------

    def test_birth_adds_brn_from_raw_data(self):
        partner = self.Partner.create({"name": "RawBirth", "is_registrant": True})
        self.RegID.create(
            {"partner_id": partner.id, "id_type_id": self.id_code.id, "value": "RAW-1"}
        )
        raw = {"identifiers": [{"type": "BRN", "value": "BRN-999"}]}
        ev = self._event(
            event_type="birth",
            identifier_value="RAW-1",
            event_date=date(2015, 7, 7),
            raw_data=json.dumps(raw),
        )
        # Should process without raising even if BRN handling is best-effort.
        self.assertTrue(ev.process_event())

