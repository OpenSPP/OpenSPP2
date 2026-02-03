"""Tests for spp_cr_types_advanced module."""

from odoo.tests import tagged

from odoo.addons.spp_change_request_v2.tests.common import CRTestCase


@tagged("post_install", "-at_install")
class TestCRTypesAdvanced(CRTestCase):
    """Test advanced CR types (Python-only types)."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.CRType = cls.env["spp.change.request.type"]
        cls.CR = cls.env["spp.change.request"]

    def test_01_add_member_type_exists(self):
        """Test that Add Member CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "add_member")], limit=1)
        self.assertTrue(cr_type, "Add Member type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertEqual(cr_type.apply_model, "spp.cr.apply.add_member")
        self.assertFalse(cr_type.is_studio_editable)
        self.assertFalse(cr_type.is_studio_cloneable)
        self.assertTrue(cr_type.is_system_type)
        self.assertEqual(cr_type.source_module, "spp_cr_types_advanced")
        self.assertTrue(cr_type.locked_reason)

    def test_02_remove_member_type_exists(self):
        """Test that Remove Member CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "remove_member")], limit=1)
        self.assertTrue(cr_type, "Remove Member type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertFalse(cr_type.is_studio_editable)
        self.assertTrue(cr_type.is_system_type)

    def test_03_change_hoh_type_exists(self):
        """Test that Change HoH CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "change_hoh")], limit=1)
        self.assertTrue(cr_type, "Change HoH type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertFalse(cr_type.is_studio_editable)

    def test_04_transfer_member_type_exists(self):
        """Test that Transfer Member CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "transfer_member")], limit=1)
        self.assertTrue(cr_type, "Transfer Member type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertFalse(cr_type.is_studio_editable)

    def test_05_exit_registrant_type_exists(self):
        """Test that Exit Registrant CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "exit_registrant")], limit=1)
        self.assertTrue(cr_type, "Exit Registrant type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertEqual(cr_type.target_type, "both")
        self.assertFalse(cr_type.is_studio_editable)

    def test_06_create_group_type_exists(self):
        """Test that Create Group CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "create_group")], limit=1)
        self.assertTrue(cr_type, "Create Group type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertFalse(cr_type.is_studio_editable)

    def test_07_split_household_type_exists(self):
        """Test that Split Household CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "split_household")], limit=1)
        self.assertTrue(cr_type, "Split Household type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertFalse(cr_type.is_studio_editable)

    def test_08_merge_registrants_type_exists(self):
        """Test that Merge Registrants CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "merge_registrants")], limit=1)
        self.assertTrue(cr_type, "Merge Registrants type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertEqual(cr_type.target_type, "both")
        self.assertFalse(cr_type.is_studio_editable)

    def test_09_all_advanced_types_have_locked_reason(self):
        """Test that all advanced types have a locked_reason."""
        advanced_codes = [
            "add_member",
            "remove_member",
            "change_hoh",
            "transfer_member",
            "exit_registrant",
            "create_group",
            "split_household",
            "merge_registrants",
        ]
        for code in advanced_codes:
            cr_type = self.CRType.search([("code", "=", code)], limit=1)
            self.assertTrue(
                cr_type.locked_reason,
                f"Type {code} should have a locked_reason",
            )
