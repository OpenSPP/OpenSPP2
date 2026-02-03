"""Tests for spp_cr_types_base module."""

from odoo.tests import tagged

from odoo.addons.spp_change_request_v2.tests.common import CRTestCase


@tagged("post_install", "-at_install")
class TestCRTypesBase(CRTestCase):
    """Test base CR types (Edit Individual, Edit Group, Update ID)."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.CRType = cls.env["spp.change.request.type"]
        cls.CR = cls.env["spp.change.request"]

    def test_01_edit_individual_type_exists(self):
        """Test that Edit Individual CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "edit_individual")], limit=1)
        self.assertTrue(cr_type, "Edit Individual type should exist")
        self.assertEqual(cr_type.apply_strategy, "field_mapping")
        self.assertTrue(cr_type.is_studio_editable)
        self.assertTrue(cr_type.is_studio_cloneable)
        self.assertTrue(cr_type.is_system_type)
        self.assertEqual(cr_type.source_module, "spp_cr_types_base")

    def test_02_edit_group_type_exists(self):
        """Test that Edit Group CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "edit_group")], limit=1)
        self.assertTrue(cr_type, "Edit Group type should exist")
        self.assertEqual(cr_type.apply_strategy, "field_mapping")
        self.assertTrue(cr_type.is_studio_editable)
        self.assertTrue(cr_type.is_studio_cloneable)
        self.assertTrue(cr_type.is_system_type)

    def test_03_update_id_type_exists(self):
        """Test that Update ID CR type is installed."""
        cr_type = self.CRType.search([("code", "=", "update_id")], limit=1)
        self.assertTrue(cr_type, "Update ID type should exist")
        self.assertEqual(cr_type.apply_strategy, "custom")
        self.assertEqual(cr_type.apply_model, "spp.cr.apply.update_id")
        self.assertTrue(cr_type.is_studio_editable)
        self.assertTrue(cr_type.is_studio_cloneable)
        self.assertTrue(cr_type.is_system_type)

    def test_04_edit_individual_field_mappings(self):
        """Test that Edit Individual has correct field mappings."""
        cr_type = self.CRType.search([("code", "=", "edit_individual")], limit=1)
        self.assertTrue(cr_type.apply_mapping_ids)
        mapping_fields = cr_type.apply_mapping_ids.mapped("source_field")
        expected_fields = [
            "given_name",
            "family_name",
            "birthdate",
            "gender_id",
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "postal_code",
        ]
        for field in expected_fields:
            self.assertIn(field, mapping_fields, f"Field {field} should be mapped")

    def test_05_edit_group_field_mappings(self):
        """Test that Edit Group has correct field mappings."""
        cr_type = self.CRType.search([("code", "=", "edit_group")], limit=1)
        self.assertTrue(cr_type.apply_mapping_ids)
        mapping_fields = cr_type.apply_mapping_ids.mapped("source_field")
        expected_fields = [
            "group_name",
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "postal_code",
        ]
        for field in expected_fields:
            self.assertIn(field, mapping_fields, f"Field {field} should be mapped")

    def test_06_edit_individual_prefill(self):
        """Test that Edit Individual detail pre-fills from registrant."""
        cr_type = self.CRType.search([("code", "=", "edit_individual")], limit=1)
        # Create a test individual
        individual = self.env["res.partner"].create(
            {
                "name": "Test Individual",
                "given_name": "Test",
                "family_name": "Individual",
                "phone": "1234567890",
                "email": "test@example.com",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a CR and get its detail record
        cr = self.CR.create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": individual.id,
            }
        )
        detail = cr.get_detail()

        # Trigger onchange to prefill
        detail._onchange_registrant_id()

        # Verify prefill
        self.assertEqual(detail.given_name, "Test")
        self.assertEqual(detail.family_name, "Individual")
        self.assertEqual(detail.phone, "1234567890")
        self.assertEqual(detail.email, "test@example.com")

    def test_07_edit_group_prefill(self):
        """Test that Edit Group detail pre-fills from registrant."""
        cr_type = self.CRType.search([("code", "=", "edit_group")], limit=1)
        # Create a test group
        group = self.env["res.partner"].create(
            {
                "name": "Test Group",
                "phone": "9876543210",
                "email": "group@example.com",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create a CR and get its detail record
        cr = self.CR.create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": group.id,
            }
        )
        detail = cr.get_detail()

        # Trigger onchange to prefill
        detail._onchange_registrant_id()

        # Verify prefill
        self.assertEqual(detail.group_name, "Test Group")
        self.assertEqual(detail.phone, "9876543210")
        self.assertEqual(detail.email, "group@example.com")
