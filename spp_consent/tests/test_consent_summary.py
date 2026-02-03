# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for consent_summary cache on registrants.

The consent_summary field provides O(1) consent lookups for API filtering.
"""

import logging
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestConsentSummary(TransactionCase):
    """Tests for consent_summary computed field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get or create test org types
        cls.org_type_ngo = cls.env.ref("spp_consent.org_type_ngo", raise_if_not_found=False) or cls.env[
            "spp.consent.org.type"
        ].create({"name": "NGO", "code": "ngo"})

        cls.org_type_gov = cls.env.ref("spp_consent.org_type_government", raise_if_not_found=False) or cls.env[
            "spp.consent.org.type"
        ].create({"name": "Government", "code": "government"})

        # Get or create test purposes
        cls.purpose_service = cls.env.ref("spp_consent.purpose_service_delivery", raise_if_not_found=False) or cls.env[
            "spp.consent.purpose"
        ].create({"name": "Service Delivery", "code": "service_delivery"})

        cls.purpose_research = cls.env.ref("spp_consent.purpose_research", raise_if_not_found=False) or cls.env[
            "spp.consent.purpose"
        ].create({"name": "Research", "code": "ResearchAndDevelopment"})

        # Get or create test personal data category
        cls.data_identity = cls.env.ref("spp_consent.data_identifying", raise_if_not_found=False) or cls.env[
            "spp.consent.personal.data"
        ].create({"name": "Identifying Information", "code": "identifying"})

        # Create data controller
        cls.controller = cls.env["res.partner"].create(
            {
                "name": "Test Controller",
                "is_company": True,
            }
        )

    def _create_consent(self, registrant, **kwargs):
        """Helper to create consent with required fields."""
        defaults = {
            "name": "Test Consent",
            "signatory_id": registrant.id,
            "status": "given",
            "effective_date": fields.Date.today(),
            "expiry": fields.Date.today() + timedelta(days=365),  # 1 year expiry
            "legal_basis": "consent",
            "controller_id": self.controller.id,
            "purpose_ids": [(6, 0, [self.purpose_service.id])],
            "personal_data_ids": [(6, 0, [self.data_identity.id])],
            "recipient_mode": "category",
            "allowed_recipient_types": [(6, 0, [self.org_type_ngo.id])],
        }
        defaults.update(kwargs)
        return self.env["spp.consent"].create(defaults)

    def _get_summary(self, registrant):
        """Helper to get consent summary, handling Odoo's False for empty Json."""
        # Invalidate cache to ensure we get fresh computed value
        registrant.invalidate_recordset(["consent_summary"])
        summary = registrant.consent_summary
        # Json field returns False when empty/not computed
        return summary if summary else {}

    def test_summary_empty_when_no_consents(self):
        """Registrant with no consents has empty summary."""
        summary = self._get_summary(self.registrant)
        self.assertEqual(summary, {})

    def test_summary_includes_org_types_from_category_consent(self):
        """Summary includes org types from category-based consents."""
        self._create_consent(
            self.registrant,
            allowed_recipient_types=[(6, 0, [self.org_type_ngo.id, self.org_type_gov.id])],
        )

        summary = self._get_summary(self.registrant)

        self.assertIn("organization_types", summary)
        self.assertIn("ngo", summary["organization_types"])
        self.assertIn("government", summary["organization_types"])

    def test_summary_includes_purposes(self):
        """Summary includes purpose codes from consents."""
        self._create_consent(
            self.registrant,
            purpose_ids=[(6, 0, [self.purpose_service.id, self.purpose_research.id])],
        )

        summary = self._get_summary(self.registrant)

        self.assertIn("purposes", summary)
        self.assertIn("service_delivery", summary["purposes"])
        self.assertIn("ResearchAndDevelopment", summary["purposes"])

    def test_summary_includes_specific_recipients(self):
        """Summary includes specific recipient IDs from specific-mode consents."""
        recipient = self.env["res.partner"].create(
            {
                "name": "Specific Recipient Org",
                "is_company": True,
            }
        )

        self._create_consent(
            self.registrant,
            recipient_mode="specific",
            recipient_ids=[(6, 0, [recipient.id])],
            allowed_recipient_types=[(5, 0, 0)],  # Clear category types
        )

        summary = self._get_summary(self.registrant)

        self.assertIn("specific_recipients", summary)
        self.assertIn(recipient.id, summary["specific_recipients"])

    def test_summary_excludes_expired_consents(self):
        """Expired consents are not included in summary."""
        yesterday = fields.Date.today() - timedelta(days=1)

        self._create_consent(
            self.registrant,
            expiry=yesterday,
            purpose_ids=[(6, 0, [self.purpose_research.id])],
            allowed_recipient_types=[(6, 0, [self.org_type_gov.id])],
        )

        summary = self._get_summary(self.registrant)

        # Should be empty since consent is expired
        self.assertEqual(summary, {})

    def test_summary_excludes_withdrawn_consents(self):
        """Withdrawn consents are not included in summary."""
        consent = self._create_consent(self.registrant)
        consent.write(
            {
                "status": "withdrawn",
                "withdrawal_reason": "Test withdrawal",
            }
        )

        summary = self._get_summary(self.registrant)

        # Should be empty since consent is withdrawn
        self.assertEqual(summary, {})

    def test_summary_aggregates_multiple_consents(self):
        """Summary aggregates data from multiple valid consents."""
        # First consent: NGO org type, service delivery purpose
        self._create_consent(
            self.registrant,
            allowed_recipient_types=[(6, 0, [self.org_type_ngo.id])],
            purpose_ids=[(6, 0, [self.purpose_service.id])],
        )

        # Second consent: Government org type, research purpose
        self._create_consent(
            self.registrant,
            name="Test Consent 2",
            allowed_recipient_types=[(6, 0, [self.org_type_gov.id])],
            purpose_ids=[(6, 0, [self.purpose_research.id])],
        )

        summary = self._get_summary(self.registrant)

        # Should have both org types and both purposes
        self.assertIn("ngo", summary["organization_types"])
        self.assertIn("government", summary["organization_types"])
        self.assertIn("service_delivery", summary["purposes"])
        self.assertIn("ResearchAndDevelopment", summary["purposes"])

    def test_summary_includes_last_updated(self):
        """Summary includes timestamp of last computation."""
        self._create_consent(self.registrant)

        summary = self._get_summary(self.registrant)

        self.assertIn("last_updated", summary)
        self.assertIsInstance(summary["last_updated"], str)

    def test_summary_renewed_consent_included(self):
        """Renewed consents are included in summary."""
        consent = self._create_consent(self.registrant)
        consent.write({"status": "renewed"})

        summary = self._get_summary(self.registrant)

        # Should include data from renewed consent
        self.assertIn("ngo", summary.get("organization_types", []))
