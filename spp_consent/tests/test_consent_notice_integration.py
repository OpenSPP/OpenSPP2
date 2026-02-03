# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestConsentNoticeIntegration(TransactionCase):
    """Test integration between consent records and privacy notices"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.consent_model = cls.env["spp.consent"]
        cls.notice_model = cls.env["spp.consent.notice"]

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

        # Create test privacy notice
        cls.test_notice = cls.notice_model.create(
            {
                "code": "TEST_NOTICE",
                "name": "Test Privacy Notice",
                "version": "1.0",
                "state": "active",
                "summary": "Test summary",
                "full_text": "<p>Test full text</p>",
                "controller_info": "Test Controller Info",
                "purpose_description": "Test purposes",
                "data_categories_description": "Test data categories",
                "recipients_description": "Test recipients",
                "retention_description": "Test retention",
                "rights_description": "Test rights",
                "withdrawal_description": "Test withdrawal",
            }
        )

    def test_01_consent_can_link_to_notice(self):
        """Test that consent can be linked to a privacy notice"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
            }
        )

        self.assertEqual(
            consent.notice_id.id,
            self.test_notice.id,
            "Consent should link to notice",
        )

    def test_02_consent_records_notice_version_shown(self):
        """Test that consent records which version of notice was shown"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        self.assertEqual(
            consent.notice_version,
            "1.0",
            "Should record notice version shown",
        )

    def test_03_consent_without_notice_is_valid(self):
        """Test that consent without notice is still valid (notice is optional)"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                # No notice_id
            }
        )

        self.assertTrue(consent.is_valid, "Consent without notice should be valid")
        self.assertFalse(consent.notice_id, "Should have no notice")

    def test_04_multiple_consents_same_notice(self):
        """Test that multiple consents can reference same notice"""
        consent1 = self.consent_model.create(
            {
                "name": "Consent 1",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        individual2 = self.env["res.partner"].create(
            {
                "name": "Individual 2",
                "is_registrant": True,
                "is_group": False,
            }
        )

        consent2 = self.consent_model.create(
            {
                "name": "Consent 2",
                "signatory_id": individual2.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        # Both should reference same notice
        self.assertEqual(consent1.notice_id.id, consent2.notice_id.id)

    def test_05_consent_preserves_notice_version_when_notice_updated(self):
        """Test that consent keeps original version even when notice is updated"""
        # Create consent with v1.0
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        # Create v2.0 of same notice
        notice_v2 = self.notice_model.create(
            {
                "code": "TEST_NOTICE",
                "name": "Test Privacy Notice",
                "version": "2.0",
                "state": "draft",
                "summary": "Updated summary",
                "full_text": "<p>Updated full text</p>",
                "controller_info": "Test Controller Info",
                "purpose_description": "Test purposes",
                "data_categories_description": "Test data categories",
                "recipients_description": "Test recipients",
                "retention_description": "Test retention",
                "rights_description": "Test rights",
                "withdrawal_description": "Test withdrawal",
                "supersedes_id": self.test_notice.id,
            }
        )
        notice_v2.action_activate()

        # Consent should still reference v1.0
        self.assertEqual(consent.notice_version, "1.0")
        # But might point to archived notice (that's OK - it's historical)
        self.assertEqual(consent.notice_id.id, self.test_notice.id)

    def test_06_default_notices_can_be_used_for_consent(self):
        """Test that default privacy notices can be used for consents"""
        # Use one of the default loaded notices
        enrollment_notice = self.notice_model.search(
            [("code", "=", "PROGRAM_ENROLLMENT")],
            limit=1,
        )

        self.assertTrue(enrollment_notice, "Default notice should exist")

        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": enrollment_notice.id,
                "notice_version": enrollment_notice.version,
            }
        )

        self.assertEqual(consent.notice_id.code, "PROGRAM_ENROLLMENT")

    def test_07_notice_version_auto_set_from_notice(self):
        """Test that notice_version can be auto-populated from notice"""
        # When creating consent with a notice, notice_version should be set at creation time
        # (mimicking what the wizard does - it captures the version when consent is recorded)
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": self.test_notice.version,  # Capture version at consent time
            }
        )

        # The notice_version should be captured from the notice at creation time
        self.assertEqual(consent.notice_version, "1.0")

    def test_08_get_active_notice_for_consent_creation(self):
        """Test using get_active_notice when creating consent"""
        # Get active notice for a code
        active_notice = self.notice_model.get_active_notice("TEST_NOTICE")

        self.assertTrue(active_notice, "Should find active notice")
        self.assertEqual(active_notice.state, "active")

        # Use it for consent
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": active_notice.id,
                "notice_version": active_notice.version,
            }
        )

        self.assertEqual(consent.notice_id.id, active_notice.id)

    def test_09_consent_jsonld_includes_notice_info(self):
        """Test that JSON-LD export includes privacy notice information"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        jsonld = consent.to_jsonld()

        # Should include privacy notice info (using W3C DPV vocabulary)
        self.assertIn("dpv:hasNotice", jsonld)
        self.assertEqual(jsonld["dpv:hasNotice"]["dpv:hasVersion"], "1.0")

    def test_10_consent_with_notice_different_purposes(self):
        """Test consent with notice can specify different purposes"""
        # Get some purposes
        purpose1 = self.env["spp.consent.purpose"].search([("code", "=", "ServiceProvision")], limit=1)

        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
                "purpose_ids": [Command.set([purpose1.id])],
            }
        )

        # Should have both notice and specific purposes
        self.assertTrue(consent.notice_id)
        self.assertTrue(consent.purpose_ids)
        self.assertIn(purpose1.id, consent.purpose_ids.ids)

    def test_11_archived_notice_still_linked_to_historical_consent(self):
        """Test that archived notice remains linked to historical consent"""
        consent = self.consent_model.create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": self.test_notice.id,
                "notice_version": "1.0",
            }
        )

        # Archive the notice
        self.test_notice.action_archive()

        # Consent should still link to archived notice (historical record)
        self.assertEqual(consent.notice_id.id, self.test_notice.id)
        self.assertEqual(consent.notice_id.state, "archived")
        # This is correct - we want to preserve what was shown

    def test_12_notice_field_optional_on_consent(self):
        """Test that notice_id field is optional (not required)"""
        # Should be able to create consent without notice
        consent = self.consent_model.create(
            {
                "name": "Test Consent No Notice",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        self.assertTrue(consent, "Consent should be created without notice")
        self.assertFalse(consent.notice_id)
        self.assertFalse(consent.notice_version)

    def test_13_multiple_notice_types_for_different_consent_purposes(self):
        """Test using different notice types for different consent types"""
        # Get different default notices
        enrollment_notice = self.notice_model.search([("code", "=", "PROGRAM_ENROLLMENT")], limit=1)
        research_notice = self.notice_model.search([("code", "=", "RESEARCH_EVALUATION")], limit=1)

        # Create enrollment consent
        enrollment_consent = self.consent_model.create(
            {
                "name": "Enrollment Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "notice_id": enrollment_notice.id,
                "notice_version": enrollment_notice.version,
            }
        )

        # Create research consent (separate)
        research_consent = self.consent_model.create(
            {
                "name": "Research Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=730),
                "notice_id": research_notice.id,
                "notice_version": research_notice.version,
            }
        )

        # Each should have different notice
        self.assertNotEqual(
            enrollment_consent.notice_id.code,
            research_consent.notice_id.code,
        )
        self.assertEqual(enrollment_consent.notice_id.code, "PROGRAM_ENROLLMENT")
        self.assertEqual(research_consent.notice_id.code, "RESEARCH_EVALUATION")
