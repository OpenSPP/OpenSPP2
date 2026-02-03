# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for consent immutability after consent is given.

Once consent transitions from 'requested' to any other status,
the substantive consent terms become immutable to ensure legal integrity.
"""

import base64
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestConsentImmutability(TransactionCase):
    """Test that consent records become immutable after consent is given."""

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

        cls.other_controller = cls.env["res.partner"].create(
            {
                "name": "Other Controller",
            }
        )

        cls.purpose = cls.env["spp.consent.purpose"].create(
            {
                "name": "Service Delivery",
                "code": "service_delivery",
            }
        )

        cls.other_purpose = cls.env["spp.consent.purpose"].create(
            {
                "name": "Research",
                "code": "research",
            }
        )

    def _create_given_consent(self):
        """Helper to create a consent that is already given."""
        return self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "expiry": date.today() + timedelta(days=365),
                "legal_basis": "consent",
            }
        )

    def _create_requested_consent(self):
        """Helper to create a consent in requested state."""
        return self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "requested",
                "expiry": date.today() + timedelta(days=365),
                "legal_basis": "consent",
            }
        )

    # =========================================================================
    # Test: Consent in 'requested' status CAN be modified
    # =========================================================================

    def test_requested_consent_can_modify_controller(self):
        """Test that controller can be changed while consent is requested."""
        consent = self._create_requested_consent()
        consent.write({"controller_id": self.other_controller.id})
        self.assertEqual(consent.controller_id, self.other_controller)

    def test_requested_consent_can_modify_purposes(self):
        """Test that purposes can be changed while consent is requested."""
        consent = self._create_requested_consent()
        consent.write({"purpose_ids": [(6, 0, [self.purpose.id])]})
        self.assertIn(self.purpose, consent.purpose_ids)

    def test_requested_consent_can_modify_legal_basis(self):
        """Test that legal basis can be changed while consent is requested."""
        consent = self._create_requested_consent()
        consent.write({"legal_basis": "public_interest"})
        self.assertEqual(consent.legal_basis, "public_interest")

    # =========================================================================
    # Test: Consent in 'given' status CANNOT modify protected fields
    # =========================================================================

    def test_given_consent_cannot_modify_controller(self):
        """Test that controller cannot be changed after consent is given."""
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write({"controller_id": self.other_controller.id})
        self.assertIn("Cannot modify consent terms", str(cm.exception))
        self.assertIn("controller_id", str(cm.exception))

    def test_given_consent_cannot_modify_signatory(self):
        """Test that signatory cannot be changed after consent is given."""
        other_individual = self.env["res.partner"].create(
            {
                "name": "Other Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write({"signatory_id": other_individual.id})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    def test_given_consent_cannot_modify_purposes(self):
        """Test that purposes cannot be changed after consent is given."""
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write({"purpose_ids": [(6, 0, [self.other_purpose.id])]})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    def test_given_consent_cannot_modify_legal_basis(self):
        """Test that legal basis cannot be changed after consent is given."""
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write({"legal_basis": "public_interest"})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    def test_given_consent_cannot_modify_expiry(self):
        """Test that expiry date cannot be changed after consent is given."""
        consent = self._create_given_consent()
        new_expiry = date.today() + timedelta(days=730)
        with self.assertRaises(UserError) as cm:
            consent.write({"expiry": new_expiry})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    def test_given_consent_cannot_modify_effective_date(self):
        """Test that effective date cannot be changed after consent is given."""
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write({"effective_date": date.today() - timedelta(days=30)})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    # =========================================================================
    # Test: Consent in 'given' status CAN modify non-protected fields
    # =========================================================================

    def test_given_consent_can_add_evidence(self):
        """Test that evidence attachment can be added after consent is given."""
        consent = self._create_given_consent()
        # Should not raise - evidence can be uploaded after consent is given
        fake_pdf_data = base64.b64encode(b"%PDF-1.4 fake pdf content").decode("utf-8")
        consent.write({"evidence_attachment": fake_pdf_data})
        self.assertTrue(consent.evidence_attachment)

    def test_given_consent_can_update_withdrawal_uri(self):
        """Test that withdrawal URI can be updated after consent is given."""
        consent = self._create_given_consent()
        # Should not raise
        consent.write({"withdrawal_uri": "https://example.com/withdraw"})
        self.assertEqual(consent.withdrawal_uri, "https://example.com/withdraw")

    def test_given_consent_can_update_withdrawal_instructions(self):
        """Test that withdrawal instructions can be updated after consent is given."""
        consent = self._create_given_consent()
        # Should not raise
        consent.write({"withdrawal_instructions": "Call our hotline to withdraw."})
        self.assertEqual(consent.withdrawal_instructions, "Call our hotline to withdraw.")

    # =========================================================================
    # Test: Status transitions are still allowed via action methods
    # =========================================================================

    def test_given_consent_can_be_withdrawn(self):
        """Test that consent can be withdrawn (status change is allowed)."""
        consent = self._create_given_consent()
        consent.action_withdraw(reason="No longer needed")
        self.assertEqual(consent.status, "withdrawn")

    def test_given_consent_can_be_renewed(self):
        """Test that consent can be renewed (status change is allowed)."""
        consent = self._create_given_consent()
        consent.action_renew()
        self.assertEqual(consent.status, "renewed")

    # =========================================================================
    # Test: Other non-requested statuses are also immutable
    # =========================================================================

    def test_withdrawn_consent_cannot_modify_controller(self):
        """Test that withdrawn consent cannot modify protected fields."""
        consent = self._create_given_consent()
        consent.action_withdraw()

        with self.assertRaises(UserError) as cm:
            consent.write({"controller_id": self.other_controller.id})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    def test_renewed_consent_cannot_modify_legal_basis(self):
        """Test that renewed consent cannot modify protected fields."""
        consent = self._create_given_consent()
        consent.action_renew()

        with self.assertRaises(UserError) as cm:
            consent.write({"legal_basis": "contract"})
        self.assertIn("Cannot modify consent terms", str(cm.exception))

    # =========================================================================
    # Test: Error message includes the attempted fields
    # =========================================================================

    def test_error_message_includes_field_names(self):
        """Test that error message lists the fields that were attempted to modify."""
        consent = self._create_given_consent()
        with self.assertRaises(UserError) as cm:
            consent.write(
                {
                    "controller_id": self.other_controller.id,
                    "legal_basis": "contract",
                }
            )
        error_message = str(cm.exception)
        self.assertIn("controller_id", error_message)
        self.assertIn("legal_basis", error_message)
