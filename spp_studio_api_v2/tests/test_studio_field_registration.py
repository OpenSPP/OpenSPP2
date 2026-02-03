# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Studio field API registration."""

from odoo.tests.common import TransactionCase


class TestStudioFieldRegistration(TransactionCase):
    """Test cases for automatic Studio field API registration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get the Studio extensions
        cls.individual_extension = cls.env.ref(
            "spp_studio_api_v2.api_extension_studio_individual",
            raise_if_not_found=False,
        )
        cls.group_extension = cls.env.ref(
            "spp_studio_api_v2.api_extension_studio_group",
            raise_if_not_found=False,
        )

        # Create a placement zone for testing
        cls.placement_zone = cls.env["spp.studio.placement.zone"].search([("target_type", "=", "individual")], limit=1)
        if not cls.placement_zone:
            cls.placement_zone = cls.env["spp.studio.placement.zone"].create(
                {
                    "name": "Test Zone",
                    "code": "test_zone",
                    "target_type": "individual",
                    "tab_name": "Test",
                    "xpath_expression": "//page[@name='test']",
                    "xpath_position": "inside",
                }
            )

    def test_extensions_created(self):
        """Test that Studio extensions are created on module install."""
        self.assertTrue(
            self.individual_extension,
            "Studio Individual extension should exist",
        )
        self.assertTrue(
            self.group_extension,
            "Studio Group extension should exist",
        )

    def test_field_auto_registration_on_activate(self):
        """Test that Studio fields are registered in API extension on activation."""
        if not self.individual_extension:
            self.skipTest("Studio extensions not available")

        # Create a Studio field
        field = self.env["spp.studio.field"].create(
            {
                "label": "Test API Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.placement_zone.id,
                "api_exposed": True,
            }
        )

        # Count fields before activation
        fields_before = len(self.individual_extension.field_ids)

        # Activate the field
        field.action_activate()

        # Verify field was added to extension
        self.individual_extension.invalidate_recordset()
        fields_after = len(self.individual_extension.field_ids)

        self.assertEqual(
            fields_after,
            fields_before + 1,
            "Field should be added to extension on activation",
        )

        # Verify the correct field was added
        self.assertIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
            "The activated field should be in the extension",
        )

    def test_field_unregistration_on_deactivate(self):
        """Test that Studio fields are unregistered from API extension on deactivation."""
        if not self.individual_extension:
            self.skipTest("Studio extensions not available")

        # Create and activate a field
        field = self.env["spp.studio.field"].create(
            {
                "label": "Test Deactivate Field",
                "field_type": "integer",
                "target_type": "individual",
                "placement_zone_id": self.placement_zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()

        # Verify field is in extension
        self.assertIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
        )

        # Deactivate the field
        field.action_deactivate()

        # Verify field was removed from extension
        self.individual_extension.invalidate_recordset()
        self.assertNotIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
            "Field should be removed from extension on deactivation",
        )

    def test_api_exposed_false_skips_registration(self):
        """Test that fields with api_exposed=False are not registered."""
        if not self.individual_extension:
            self.skipTest("Studio extensions not available")

        # Create a Studio field with api_exposed=False
        field = self.env["spp.studio.field"].create(
            {
                "label": "Private Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.placement_zone.id,
                "api_exposed": False,
            }
        )

        # Activate the field
        field.action_activate()

        # Verify field was NOT added to extension
        self.individual_extension.invalidate_recordset()
        self.assertNotIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
            "Field with api_exposed=False should not be in extension",
        )

    def test_toggle_api_exposed_updates_registration(self):
        """Test that changing api_exposed updates registration."""
        if not self.individual_extension:
            self.skipTest("Studio extensions not available")

        # Create and activate a field with api_exposed=True
        field = self.env["spp.studio.field"].create(
            {
                "label": "Toggle Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.placement_zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()

        # Verify in extension
        self.assertIn(field.ir_model_fields_id, self.individual_extension.field_ids)

        # Toggle api_exposed to False
        field.with_context(force_write=True).write({"api_exposed": False})

        # Verify removed from extension
        self.individual_extension.invalidate_recordset()
        self.assertNotIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
        )

        # Toggle back to True
        field.with_context(force_write=True).write({"api_exposed": True})

        # Verify added back to extension
        self.individual_extension.invalidate_recordset()
        self.assertIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
        )

    def test_group_field_registration(self):
        """Test that group fields register to the group extension."""
        if not self.group_extension:
            self.skipTest("Studio extensions not available")

        # Get or create a group placement zone
        group_zone = self.env["spp.studio.placement.zone"].search([("target_type", "=", "group")], limit=1)
        if not group_zone:
            group_zone = self.env["spp.studio.placement.zone"].create(
                {
                    "name": "Test Group Zone",
                    "code": "test_group_zone",
                    "target_type": "group",
                    "tab_name": "Test",
                    "xpath_expression": "//page[@name='test']",
                    "xpath_position": "inside",
                }
            )

        # Create and activate a group field
        field = self.env["spp.studio.field"].create(
            {
                "label": "Group Test Field",
                "field_type": "text",
                "target_type": "group",
                "placement_zone_id": group_zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()

        # Verify field is in group extension (not individual)
        self.group_extension.invalidate_recordset()
        self.individual_extension.invalidate_recordset()

        self.assertIn(
            field.ir_model_fields_id,
            self.group_extension.field_ids,
            "Group field should be in group extension",
        )
        self.assertNotIn(
            field.ir_model_fields_id,
            self.individual_extension.field_ids,
            "Group field should not be in individual extension",
        )
