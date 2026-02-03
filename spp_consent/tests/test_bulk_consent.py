# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test bulk consent recording functionality."""

from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestBulkConsent(TransactionCase):
    """Test bulk consent recording functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create multiple registrants for bulk operations
        cls.registrant1 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 1",
                "is_registrant": True,
            }
        )
        cls.registrant2 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
            }
        )
        cls.registrant3 = cls.env["res.partner"].create(
            {
                "name": "Test Registrant 3",
                "is_registrant": True,
            }
        )

        # Create a non-registrant for testing filtering
        cls.non_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Non-Registrant",
                "is_registrant": False,
            }
        )

        # Create test controller
        cls.controller = cls.env["res.partner"].create(
            {
                "name": "Test Controller",
            }
        )

        # Create test purpose
        cls.purpose1 = cls.env["spp.consent.purpose"].create(
            {
                "name": "Service Delivery",
                "code": "service_delivery",
            }
        )

        # Create test personal data category
        cls.personal_data1 = cls.env["spp.consent.personal.data"].create(
            {
                "name": "Contact Information",
                "code": "contact_info",
            }
        )

    def _create_bulk_wizard(self, registrant_ids, **kwargs):
        """Helper to create bulk consent wizard with common defaults.

        Args:
            registrant_ids: List of registrant IDs
            **kwargs: Additional fields to override defaults

        Returns:
            Wizard record
        """
        vals = {
            "registrant_ids": [Command.set(registrant_ids)],
            "expiry": date.today() + timedelta(days=365),
            "purpose_ids": [Command.set([self.purpose1.id])],
            "personal_data_ids": [Command.set([self.personal_data1.id])],
            "legal_basis": "consent",
            "controller_id": self.controller.id,
            "collection_method": "written",
        }
        vals.update(kwargs)
        return self.env["spp.bulk.record.consent.wizard"].create(vals)

    def test_bulk_record_consent_creates_multiple_records(self):
        """Test that bulk wizard creates consent for all selected beneficiaries."""
        wizard = self._create_bulk_wizard([self.registrant1.id, self.registrant2.id, self.registrant3.id])
        wizard.action_record_bulk_consent()

        # Verify consent created for all 3 registrants
        consents = self.env["spp.consent"].search(
            [("signatory_id", "in", [self.registrant1.id, self.registrant2.id, self.registrant3.id])]
        )

        self.assertEqual(len(consents), 3, "Should create 3 consent records")

        # Verify all have same parameters
        for consent in consents:
            self.assertEqual(consent.legal_basis, "consent")
            self.assertEqual(consent.purpose_ids, self.purpose1)
            self.assertEqual(consent.personal_data_ids, self.personal_data1)
            self.assertEqual(consent.status, "given")

    def test_bulk_consent_validates_expiry_date(self):
        """Test that bulk wizard validates expiry date."""
        with self.assertRaises(ValidationError, msg="Should reject past expiry date"):
            self._create_bulk_wizard(
                [self.registrant1.id],
                expiry=date.today() - timedelta(days=1),  # Past date
            )

    def test_bulk_consent_requires_beneficiaries(self):
        """Test that bulk wizard requires at least one beneficiary."""
        wizard = self._create_bulk_wizard([])  # Empty list

        with self.assertRaises(ValidationError, msg="Should require at least one beneficiary"):
            wizard.action_record_bulk_consent()

    def test_bulk_consent_sets_effective_date(self):
        """Test that bulk consent sets effective date to today."""
        wizard = self._create_bulk_wizard([self.registrant1.id])
        wizard.action_record_bulk_consent()

        consent = self.env["spp.consent"].search([("signatory_id", "=", self.registrant1.id)])
        self.assertEqual(consent.effective_date, date.today(), "Effective date should be today")

    def test_bulk_consent_copies_all_fields_correctly(self):
        """Test that all wizard fields are properly copied to consent records."""
        # Create a privacy notice for testing
        notice = self.env["spp.consent.notice"].create(
            {
                "name": "Test Notice",
                "code": "test_notice",
                "version": "1.0",
                "state": "active",
            }
        )

        wizard = self._create_bulk_wizard(
            [self.registrant1.id, self.registrant2.id],
            legal_basis="public_interest",
            collection_method="electronic",
            notice_id=notice.id,
        )
        wizard.action_record_bulk_consent()

        # Verify both consents have all fields set correctly
        consents = self.env["spp.consent"].search([("signatory_id", "in", [self.registrant1.id, self.registrant2.id])])
        self.assertEqual(len(consents), 2)

        for consent in consents:
            self.assertEqual(consent.legal_basis, "public_interest")
            self.assertEqual(consent.controller_id, self.controller)
            self.assertEqual(consent.collection_method, "electronic")
            self.assertEqual(consent.notice_id, notice)
            self.assertEqual(consent.notice_version, "1.0")

    def test_bulk_wizard_prepopulates_from_context(self):
        """Test that wizard pre-populates selected registrants from context."""
        wizard = (
            self.env["spp.bulk.record.consent.wizard"]
            .with_context(
                active_ids=[self.registrant1.id, self.registrant2.id, self.registrant3.id],
                active_model="res.partner",
            )
            .create(
                {
                    "expiry": date.today() + timedelta(days=365),
                    "purpose_ids": [Command.set([self.purpose1.id])],
                    "personal_data_ids": [Command.set([self.personal_data1.id])],
                    "legal_basis": "consent",
                    "controller_id": self.controller.id,
                    "collection_method": "written",
                }
            )
        )

        # Wizard should auto-populate registrant_ids from context
        self.assertEqual(len(wizard.registrant_ids), 3, "Should pre-populate 3 registrants from context")
        self.assertIn(self.registrant1, wizard.registrant_ids)
        self.assertIn(self.registrant2, wizard.registrant_ids)
        self.assertIn(self.registrant3, wizard.registrant_ids)

    def test_bulk_wizard_filters_non_registrants_from_context(self):
        """Test that wizard filters out non-registrants when pre-populating from context."""
        wizard = (
            self.env["spp.bulk.record.consent.wizard"]
            .with_context(
                active_ids=[self.registrant1.id, self.non_registrant.id, self.registrant2.id],
                active_model="res.partner",
            )
            .create(
                {
                    "expiry": date.today() + timedelta(days=365),
                    "purpose_ids": [Command.set([self.purpose1.id])],
                    "personal_data_ids": [Command.set([self.personal_data1.id])],
                    "legal_basis": "consent",
                    "controller_id": self.controller.id,
                    "collection_method": "written",
                }
            )
        )

        # Should only include registrants, not non-registrants
        self.assertEqual(len(wizard.registrant_ids), 2, "Should filter to only 2 registrants")
        self.assertIn(self.registrant1, wizard.registrant_ids)
        self.assertIn(self.registrant2, wizard.registrant_ids)
        self.assertNotIn(self.non_registrant, wizard.registrant_ids)

    def test_bulk_wizard_computes_count(self):
        """Test that wizard correctly computes beneficiary count."""
        wizard = self._create_bulk_wizard([self.registrant1.id, self.registrant2.id])
        self.assertEqual(wizard.registrant_count, 2, "Should compute count as 2")

        # Update registrants and verify count updates
        wizard.write({"registrant_ids": [Command.set([self.registrant1.id])]})
        self.assertEqual(wizard.registrant_count, 1, "Should compute count as 1 after update")

    def test_bulk_wizard_uses_batch_creation(self):
        """Test that bulk wizard uses batch creation for performance."""
        # Create 10 registrants for batch testing
        registrants = self.env["res.partner"].create(
            [{"name": f"Batch Registrant {i}", "is_registrant": True} for i in range(10)]
        )

        wizard = self._create_bulk_wizard(registrants.ids)
        wizard.action_record_bulk_consent()

        # Verify all consents were created with correct parameters
        consents = self.env["spp.consent"].search([("signatory_id", "in", registrants.ids)])
        self.assertEqual(len(consents), 10, "Should create 10 consent records")

        # Verify all have the same parameters (batch creation worked)
        for consent in consents:
            self.assertEqual(consent.legal_basis, "consent")
            self.assertEqual(consent.purpose_ids, self.purpose1)
            self.assertEqual(consent.personal_data_ids, self.personal_data1)
            self.assertEqual(consent.status, "given")
            self.assertEqual(consent.controller_id, self.controller)
