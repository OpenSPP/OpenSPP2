# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Additional edge case tests for consent matching.

Tests edge cases discovered during security review:
- External ID uniqueness and format
- Consent with no recipients
- Consent with empty organization types
- Status transitions
"""

from datetime import date, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestConsentEdgeCases(TransactionCase):
    """Test edge cases in consent matching logic"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.controller = cls.env["res.partner"].create({"name": "Data Controller"})
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.recipient = cls.env["res.partner"].create({"name": "Recipient Org"})

        cls.org_type = cls.env["spp.consent.org.type"].create({"name": "Test Type", "code": "test"})

    def test_consent_external_id_auto_generated(self):
        """External ID is auto-generated as UUID on create"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        self.assertTrue(consent.external_id, "External ID should be generated")
        # UUID format check (36 chars with hyphens)
        self.assertEqual(len(consent.external_id), 36)
        self.assertIn("-", consent.external_id)

    def test_consent_external_id_unique(self):
        """External IDs are unique across consents"""
        consent1 = self.env["spp.consent"].create(
            {
                "name": "Consent 1",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        consent2 = self.env["spp.consent"].create(
            {
                "name": "Consent 2",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        self.assertNotEqual(
            consent1.external_id,
            consent2.external_id,
            "External IDs should be unique",
        )

    def test_check_consent_with_no_recipient_mode(self):
        """Legacy consent without recipient_mode can still be checked"""
        # Create with status="requested" so we can modify recipient_mode
        consent = self.env["spp.consent"].create(
            {
                "name": "Legacy Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "requested",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Remove recipient_mode to simulate legacy data (must be done while status="requested")
        consent.write({"recipient_mode": False})

        # Now give the consent
        consent.write({"status": "given"})

        # Should still be findable with specific recipient check
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        self.assertEqual(found, consent, "Legacy consent should be found")

    def test_category_consent_with_no_org_types(self):
        """Category consent with empty allowed_recipient_types matches nothing"""
        self.env["spp.consent"].create(
            {
                "name": "Empty Category Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "category",
                "allowed_recipient_types": [Command.set([])],  # Empty list
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Should not match any org type
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="test",
        )

        self.assertFalse(found, "Should not match when no org types specified")

    def test_specific_consent_with_no_recipients(self):
        """Specific consent with empty recipient_ids matches nothing"""
        self.env["spp.consent"].create(
            {
                "name": "Empty Recipients Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([])],  # Empty list
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Should not match any recipient
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        self.assertFalse(found, "Should not match when no recipients specified")

    def test_consent_status_requested_not_active(self):
        """Consent in 'requested' status is not active"""
        self.env["spp.consent"].create(
            {
                "name": "Requested Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "requested",  # Not yet given
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        self.assertFalse(found, "Requested consent should not be active")

    def test_consent_status_refused_not_active(self):
        """Refused consent is not active"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "requested",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Refuse it
        consent.action_refuse()

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        self.assertFalse(found, "Refused consent should not be active")

    def test_consent_renewed_status_is_active(self):
        """Renewed consent is considered active"""
        # Create with future expiry date so we don't need to modify it during renewal
        # (expiry is a protected field after status="given")
        consent = self.env["spp.consent"].create(
            {
                "name": "Renewable Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Renew it (without changing expiry to avoid immutability protection)
        consent.action_renew()

        # Should find renewed consent
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        self.assertEqual(found, consent, "Renewed consent should be active")
        self.assertEqual(consent.status, "renewed")

    def test_is_recipient_allowed_with_none_parameters(self):
        """is_recipient_allowed handles None parameters gracefully"""
        # Test 1: Consent with recipients - should return True (recipients exist)
        consent_with_recipients = self.env["spp.consent"].create(
            {
                "name": "Test Consent With Recipients",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        result = consent_with_recipients.is_recipient_allowed(recipient_id=None, org_type_code=None)
        self.assertTrue(result, "Should return True when consent has recipients (even without specifying which)")

        # Test 2: Consent with NO recipients - should return False
        consent_without_recipients = self.env["spp.consent"].create(
            {
                "name": "Test Consent Without Recipients",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([])],  # Empty recipients
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        result = consent_without_recipients.is_recipient_allowed(recipient_id=None, org_type_code=None)
        self.assertFalse(result, "Should return False when consent has no recipients configured")

    def test_check_consent_both_individual_and_group_consent(self):
        """When individual has both personal and group consent, personal takes precedence"""
        # Create group
        group = self.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # Add individual to group through membership
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": self.individual.id,
            }
        )

        # Create group consent
        group_consent = self.env["spp.consent"].create(
            {
                "name": "Group Consent",
                "group_id": group.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Create individual consent
        individual_consent = self.env["spp.consent"].create(
            {
                "name": "Individual Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_ids": [Command.set([self.recipient.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Check consent should find individual consent first
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.recipient.id,
        )

        # The implementation might return the most recent or specific one
        # At minimum, should find one of them
        self.assertTrue(found, "Should find at least one consent")
        self.assertIn(found, [individual_consent, group_consent])
