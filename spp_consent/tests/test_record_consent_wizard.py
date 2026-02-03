from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError

from .common import Common


class TestRecordConsentWiz(Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Get test purposes and data categories from demo data
        cls.purpose_service = cls.env.ref("spp_consent.purpose_service_provision")
        cls.data_identifying = cls.env.ref("spp_consent.pd_identifying")

    def test_01_record_consent_raise_error(self):
        test_consent = self._model.create({"group_id": self._test_group.id})
        with self.assertRaisesRegex(UserError, ".*data subject.*signatory.*must be selected.*"):
            test_consent.record_consent()

    def test_02_record_consent(self):
        self.assertFalse(
            bool(self._test_group.consent_ids.ids),
            "Test group should not having related consent records!",
        )
        # Create with valid data: future expiry, purposes, and personal data
        future_date = fields.Date.today() + timedelta(days=365)
        test_consent_group = self._model.create(
            {
                "group_id": self._test_group.id,
                "signatory_id": self._test_individual_1.id,
                "is_group": True,
                "expiry": future_date,
                "purpose_ids": [Command.set([self.purpose_service.id])],
                "personal_data_ids": [Command.set([self.data_identifying.id])],
            }
        )
        test_consent_group.record_consent()
        self.assertTrue(
            bool(self._test_group.consent_ids.ids),
            "Test group should now having related consent records!",
        )
        self.assertFalse(
            bool(self._test_individual_1.consent_ids.ids),
            "Test individual should not having related consent records!",
        )
        test_consent_individual = self._model.create(
            {
                "signatory_id": self._test_individual_1.id,
                "expiry": future_date,
                "purpose_ids": [Command.set([self.purpose_service.id])],
                "personal_data_ids": [Command.set([self.data_identifying.id])],
            }
        )
        test_consent_individual.record_consent()
        self.assertTrue(
            bool(self._test_individual_1.consent_ids.ids),
            "Test individual should now having related consent records!",
        )

    def test_03_compute_name(self):
        future_date = fields.Date.today() + timedelta(days=365)
        test_consent = self._model.create({"signatory_id": self._test_individual_1.id, "expiry": future_date})
        self.assertEqual(
            test_consent.name,
            "Tywin Lannister",
            "Consent Wizard should have same name with its signatory!",
        )

    def test_04_get_view(self):
        arch, view = (
            self.env["spp.record.consent.wizard"]
            .with_context(active_id=self._test_group.id)
            ._get_view(view_type="form")
        )
        self.assertEqual(len(arch.xpath("//field[@name='signatory_id']")), 1)

    def test_05_get_members(self):
        consent_wizard = self._model.create({"group_id": self._test_group.id})

        members = consent_wizard._get_members()
        self.assertIn("domain", members)
        self.assertIn("signatory_id", members["domain"])
        self.assertIn(self._test_individual_1.id, members["domain"]["signatory_id"][0][2])
        self.assertIn(self._test_individual_2.id, members["domain"]["signatory_id"][0][2])
        self.assertIn(self._test_individual_3.id, members["domain"]["signatory_id"][0][2])
        self.assertIn(self._test_individual_4.id, members["domain"]["signatory_id"][0][2])
