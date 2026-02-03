# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestConsentActions(TransactionCase):
    """Test consent action methods and state transitions"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.consent_model = cls.env["spp.consent"]

        # Create test data
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.controller = cls.env["res.partner"].create(
            {
                "name": "Test Controller",
            }
        )

        cls.recipient = cls.env["res.partner"].create(
            {
                "name": "Test Recipient",
            }
        )

    def test_01_action_give_sets_status_and_date(self):
        """Test that action_give sets status to given and effective_date"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Call action_give
        consent.action_give()

        self.assertEqual(consent.status, "given", "Status should be 'given'")
        self.assertEqual(
            consent.effective_date,
            date.today(),
            "Effective date should be set to today",
        )

    def test_02_action_give_respects_provided_effective_date(self):
        """Test that action_give uses existing effective_date if already set"""
        custom_date = date.today() - timedelta(days=30)
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "effective_date": custom_date,  # Pre-set the effective date
                "expiry": date.today() + timedelta(days=365),
            }
        )

        consent.action_give()

        self.assertEqual(consent.status, "given")
        self.assertEqual(
            consent.effective_date,
            custom_date,
            "Should preserve pre-set effective_date",
        )

    def test_03_action_give_only_from_requested_status(self):
        """Test that action_give only works from 'requested' status"""
        # Create consent already given
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        original_date = consent.effective_date

        # Try to call action_give again - should not change
        consent.action_give()

        # Status should still be given, date unchanged
        self.assertEqual(consent.status, "given")
        self.assertEqual(consent.effective_date, original_date)

    def test_04_action_verify_marks_consent_verified(self):
        """Test that action_verify marks written/verbal consent as verified"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "collection_method": "written",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Initially not verified
        self.assertFalse(consent.verified_by_id, "Should not be verified initially")
        self.assertFalse(consent.verified_date, "Should not have verified date")

        # Verify the consent
        consent.action_verify()

        # Should be marked as verified
        self.assertEqual(
            consent.verified_by_id.id,
            self.env.user.id,
            "Should be verified by current user",
        )
        self.assertTrue(consent.verified_date, "Should have verified date")

    def test_05_action_verify_only_once(self):
        """Test that action_verify doesn't re-verify already verified consent"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "collection_method": "verbal",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Verify once
        consent.action_verify()
        first_verified_date = consent.verified_date
        first_verified_by = consent.verified_by_id

        # Try to verify again - should not change
        consent.action_verify()

        self.assertEqual(consent.verified_date, first_verified_date)
        self.assertEqual(consent.verified_by_id.id, first_verified_by.id)

    def test_06_create_with_given_status_auto_sets_effective_date(self):
        """Test that creating consent with status='given' auto-sets effective_date"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",  # Created as already given
                "expiry": date.today() + timedelta(days=365),
            }
        )

        self.assertEqual(
            consent.effective_date,
            date.today(),
            "Effective date should auto-set to today",
        )

    def test_07_action_give_records_history(self):
        """Test that action_give records history entry"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "expiry": date.today() + timedelta(days=365),
            }
        )

        initial_history_count = len(consent.history_ids)

        consent.action_give()

        # Should have added history entry
        self.assertGreater(
            len(consent.history_ids),
            initial_history_count,
            "Should have recorded history",
        )

    def test_08_status_transitions_complete_flow(self):
        """Test complete consent lifecycle: requested → given → withdrawn"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Step 1: requested
        self.assertEqual(consent.status, "requested")
        self.assertFalse(consent.is_valid)

        # Step 2: give consent
        consent.action_give()
        self.assertEqual(consent.status, "given")
        self.assertTrue(consent.is_valid)

        # Step 3: withdraw
        consent.action_withdraw(reason="User requested withdrawal")
        self.assertEqual(consent.status, "withdrawn")
        self.assertFalse(consent.is_valid)

    def test_09_action_give_with_recipient_mode_specific(self):
        """Test action_give works with specific recipients"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([self.recipient.id])],
                "expiry": date.today() + timedelta(days=365),
            }
        )

        consent.action_give()

        self.assertEqual(consent.status, "given")
        # Recipients should be preserved
        self.assertIn(self.recipient.id, consent.recipient_ids.ids)

    def test_10_action_give_with_recipient_mode_category(self):
        """Test action_give works with category-based recipients"""
        # Get an org type
        org_type = self.env["spp.consent.org.type"].search([("code", "=", "ngo")], limit=1)

        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "recipient_mode": "category",
                "allowed_recipient_types": [Command.set([org_type.id])],
                "expiry": date.today() + timedelta(days=365),
            }
        )

        consent.action_give()

        self.assertEqual(consent.status, "given")
        # Allowed types should be preserved
        self.assertIn(org_type.id, consent.allowed_recipient_types.ids)

    def test_11_action_verify_for_electronic_consent(self):
        """Test that electronic consent doesn't need verification"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "collection_method": "electronic",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Electronic consent can still be verified if needed (e.g., by supervisor)
        consent.action_verify()

        # Should work fine
        self.assertTrue(consent.verified_by_id)

    def test_12_refused_consent_cannot_be_given(self):
        """Test that refused consent stays refused when trying action_give"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Refuse it
        consent.action_refuse()
        self.assertEqual(consent.status, "refused")

        # Try to give it - should not work (only from requested)
        consent.action_give()

        # Should still be refused
        self.assertEqual(consent.status, "refused")
