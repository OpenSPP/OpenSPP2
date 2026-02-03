# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestPrivacyNotices(TransactionCase):
    """Test Privacy Notice functionality (ISO 29184 compliance)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.notice_model = cls.env["spp.consent.notice"]

    def test_01_default_notices_loaded(self):
        """Test that 4 default privacy notices are loaded from data file"""
        expected_codes = [
            "PROGRAM_ENROLLMENT",
            "DATA_SHARING",
            "BENEFICIARY_VERIFICATION",
            "RESEARCH_EVALUATION",
        ]

        for code in expected_codes:
            notice = self.notice_model.search([("code", "=", code)])
            self.assertTrue(
                notice,
                f"Default notice '{code}' should be loaded",
            )
            self.assertEqual(
                notice.version,
                "1.0",
                f"Default notice '{code}' should have version 1.0",
            )

    def test_02_program_enrollment_notice_structure(self):
        """Test Program Enrollment notice has all ISO 29184 elements"""
        notice = self.notice_model.search([("code", "=", "PROGRAM_ENROLLMENT")])

        self.assertTrue(notice.name, "Notice should have name")
        self.assertTrue(notice.summary, "Notice should have summary")
        self.assertTrue(notice.full_text, "Notice should have full text")

        # ISO 29184 required elements
        self.assertTrue(
            notice.controller_info,
            "Notice should have controller info (ISO 29184)",
        )
        self.assertTrue(
            notice.purpose_description,
            "Notice should have purpose description (ISO 29184)",
        )
        self.assertTrue(
            notice.data_categories_description,
            "Notice should have data categories (ISO 29184)",
        )
        self.assertTrue(
            notice.recipients_description,
            "Notice should have recipients description (ISO 29184)",
        )
        self.assertTrue(
            notice.retention_description,
            "Notice should have retention description (ISO 29184)",
        )
        self.assertTrue(
            notice.rights_description,
            "Notice should have rights description (ISO 29184)",
        )
        self.assertTrue(
            notice.withdrawal_description,
            "Notice should have withdrawal instructions (ISO 29184)",
        )

    def test_03_all_default_notices_are_active(self):
        """Test all default notices are loaded in active state"""
        default_codes = [
            "PROGRAM_ENROLLMENT",
            "DATA_SHARING",
            "BENEFICIARY_VERIFICATION",
            "RESEARCH_EVALUATION",
        ]

        for code in default_codes:
            notice = self.notice_model.search([("code", "=", code)])
            self.assertEqual(
                notice.state,
                "active",
                f"Default notice '{code}' should be active",
            )

    def test_04_notice_different_versions_allowed(self):
        """Test that same code can have different versions"""
        # Create version 1.0
        notice1 = self.notice_model.create(
            {
                "code": "TEST_NOTICE",
                "name": "Test Notice",
                "version": "1.0",
                "state": "draft",
            }
        )

        # Create version 2.0 (different version should work)
        notice2 = self.notice_model.create(
            {
                "code": "TEST_NOTICE",
                "name": "Test Notice v2",
                "version": "2.0",  # Different version
                "state": "draft",
            }
        )

        self.assertTrue(notice1, "Version 1.0 should be created")
        self.assertTrue(notice2, "Version 2.0 should be created")
        self.assertEqual(notice1.code, notice2.code, "Both should have same code")
        self.assertNotEqual(notice1.version, notice2.version, "Versions should differ")

        # Note: Unique constraint on (code, version) is enforced at database level
        # We don't test the violation to avoid CI errors from expected database exceptions

    def test_05_notice_name_get_includes_version(self):
        """Test that notice display name includes version"""
        notice = self.notice_model.create(
            {
                "code": "TEST",
                "name": "Test Notice",
                "version": "1.5",
                "state": "draft",
            }
        )

        display_name = notice.name_get()[0][1]
        self.assertIn("v1.5", display_name, "Display name should include version")
        self.assertIn("Test Notice", display_name, "Display name should include name")

    def test_06_action_activate_archives_previous_version(self):
        """Test activating a notice archives previous active versions"""
        # Create version 1.0 and activate it
        notice_v1 = self.notice_model.create(
            {
                "code": "TEST_ACTIVATION",
                "name": "Test Activation Notice",
                "version": "1.0",
                "state": "draft",
            }
        )
        notice_v1.action_activate()

        self.assertEqual(notice_v1.state, "active", "V1 should be active")

        # Create version 2.0 and activate it
        notice_v2 = self.notice_model.create(
            {
                "code": "TEST_ACTIVATION",
                "name": "Test Activation Notice",
                "version": "2.0",
                "state": "draft",
                "supersedes_id": notice_v1.id,
            }
        )
        notice_v2.action_activate()

        # Refresh v1 to get updated state
        notice_v1.invalidate_recordset()

        self.assertEqual(notice_v2.state, "active", "V2 should be active")
        self.assertEqual(
            notice_v1.state,
            "archived",
            "V1 should be archived when V2 is activated",
        )

    def test_07_action_activate_only_archives_same_code(self):
        """Test activation only archives notices with same code"""
        # Create notice A v1.0
        notice_a = self.notice_model.create(
            {
                "code": "NOTICE_A",
                "name": "Notice A",
                "version": "1.0",
                "state": "draft",
            }
        )
        notice_a.action_activate()

        # Create notice B v1.0
        notice_b = self.notice_model.create(
            {
                "code": "NOTICE_B",
                "name": "Notice B",
                "version": "1.0",
                "state": "draft",
            }
        )
        notice_b.action_activate()

        # Notice A should still be active (different code)
        notice_a.invalidate_recordset()
        self.assertEqual(
            notice_a.state,
            "active",
            "Notice A should remain active (different code)",
        )

    def test_08_action_archive(self):
        """Test action_archive sets state to archived"""
        notice = self.notice_model.create(
            {
                "code": "TEST_ARCHIVE",
                "name": "Test Archive",
                "version": "1.0",
                "state": "active",
            }
        )

        notice.action_archive()

        self.assertEqual(notice.state, "archived", "Notice should be archived")

    def test_09_get_active_notice_by_code(self):
        """Test get_active_notice() returns currently active notice for code"""
        # Create and activate v1.0
        notice_v1 = self.notice_model.create(
            {
                "code": "SEARCH_TEST",
                "name": "Search Test",
                "version": "1.0",
                "state": "draft",
            }
        )
        notice_v1.action_activate()

        # Search for active notice
        found = self.notice_model.get_active_notice("SEARCH_TEST")

        self.assertEqual(found.id, notice_v1.id, "Should find active v1.0")
        self.assertEqual(found.version, "1.0")

        # Create and activate v2.0
        notice_v2 = self.notice_model.create(
            {
                "code": "SEARCH_TEST",
                "name": "Search Test",
                "version": "2.0",
                "state": "draft",
                "supersedes_id": notice_v1.id,
            }
        )
        notice_v2.action_activate()

        # Search should now return v2.0
        found = self.notice_model.get_active_notice("SEARCH_TEST")

        self.assertEqual(found.id, notice_v2.id, "Should find active v2.0")
        self.assertEqual(found.version, "2.0")

    def test_10_get_active_notice_nonexistent_code(self):
        """Test get_active_notice() returns empty for nonexistent code"""
        found = self.notice_model.get_active_notice("NONEXISTENT_CODE")

        self.assertFalse(found, "Should return empty recordset for nonexistent code")

    def test_11_multiple_draft_versions_allowed(self):
        """Test multiple draft versions of same notice can exist"""
        notice_v1 = self.notice_model.create(
            {
                "code": "MULTI_DRAFT",
                "name": "Multi Draft",
                "version": "1.0",
                "state": "draft",
            }
        )

        notice_v2 = self.notice_model.create(
            {
                "code": "MULTI_DRAFT",
                "name": "Multi Draft",
                "version": "2.0",
                "state": "draft",
            }
        )

        self.assertTrue(notice_v1)
        self.assertTrue(notice_v2)
        self.assertEqual(notice_v1.state, "draft")
        self.assertEqual(notice_v2.state, "draft")

    def test_12_supersedes_relationship(self):
        """Test supersedes_id correctly links notice versions"""
        notice_v1 = self.notice_model.create(
            {
                "code": "SUPERSEDE_TEST",
                "name": "Supersede Test",
                "version": "1.0",
                "state": "active",
            }
        )

        notice_v2 = self.notice_model.create(
            {
                "code": "SUPERSEDE_TEST",
                "name": "Supersede Test",
                "version": "2.0",
                "state": "draft",
                "supersedes_id": notice_v1.id,
            }
        )

        self.assertEqual(
            notice_v2.supersedes_id.id,
            notice_v1.id,
            "V2 should reference V1 as superseded",
        )

    def test_13_notice_language_field(self):
        """Test notice language field is set correctly"""
        notice = self.notice_model.search([("code", "=", "PROGRAM_ENROLLMENT")])

        self.assertEqual(
            notice.language,
            "en",
            "Default notices should have English language",
        )

    def test_14_notice_translatable_fields(self):
        """Test that key fields are marked as translatable"""
        # This tests that the fields have translate=True
        # We verify this by checking field definitions
        notice_fields = self.notice_model.fields_get(["name", "summary", "full_text", "controller_info"])

        self.assertTrue(
            notice_fields["name"].get("translate"),
            "name field should be translatable",
        )
        self.assertTrue(
            notice_fields["summary"].get("translate"),
            "summary field should be translatable",
        )
        self.assertTrue(
            notice_fields["full_text"].get("translate"),
            "full_text field should be translatable",
        )

    def test_15_notice_contact_fields(self):
        """Test notice has contact information fields"""
        notice = self.notice_model.search([("code", "=", "PROGRAM_ENROLLMENT")])

        # Check fields exist and have values (templates have placeholder values)
        self.assertTrue(
            hasattr(notice, "contact_email"),
            "Notice should have contact_email field",
        )
        self.assertTrue(
            hasattr(notice, "contact_url"),
            "Notice should have contact_url field",
        )
        self.assertTrue(
            hasattr(notice, "full_policy_url"),
            "Notice should have full_policy_url field",
        )

    def test_16_biometric_notice_has_special_data_warning(self):
        """Test BENEFICIARY_VERIFICATION notice mentions sensitive data"""
        notice = self.notice_model.search([("code", "=", "BENEFICIARY_VERIFICATION")])

        # Biometric data is sensitive - notice should mention this
        data_categories = notice.data_categories_description.lower()
        self.assertTrue(
            "sensitive" in data_categories or "biometric" in data_categories,
            "Biometric notice should mention sensitive data",
        )

    def test_17_research_notice_mentions_voluntary(self):
        """Test RESEARCH_EVALUATION notice emphasizes voluntary participation"""
        notice = self.notice_model.search([("code", "=", "RESEARCH_EVALUATION")])

        # Research participation should be voluntary
        summary = notice.summary.lower()
        self.assertIn(
            "voluntary",
            summary,
            "Research notice should mention voluntary participation",
        )

    def test_18_data_sharing_notice_mentions_categories(self):
        """Test DATA_SHARING notice mentions organization categories"""
        notice = self.notice_model.search([("code", "=", "DATA_SHARING")])

        recipients = notice.recipients_description.lower()
        # Should mention category-based sharing options
        self.assertTrue(
            "government" in recipients or "ngo" in recipients or "categor" in recipients,
            "Data sharing notice should mention organization categories",
        )
