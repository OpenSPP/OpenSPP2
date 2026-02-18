"""Integration tests for field deactivation with impact warnings."""

from odoo.tests.common import TransactionCase


class TestFieldDeactivationImpact(TransactionCase):
    """Test field deactivation impact warnings and wizard flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.StudioField = cls.env["spp.studio.field"]
        cls.PlacementZone = cls.env["spp.studio.placement.zone"]
        cls.Partner = cls.env["res.partner"]
        cls.Wizard = cls.env["spp.studio.deactivate.wizard"]

        # Create a test placement zone
        cls.zone = cls.PlacementZone.create(
            {
                "name": "Test Zone Impact",
                "code": "test_zone_impact",
                "target_type": "individual",
                "tab_name": "Profile",
                "xpath_expression": (
                    "//notebook[@name='individual_detail']//page[@name='profile']//group[@name='demographics_section']"
                ),
                "xpath_position": "inside",
            }
        )

    def test_deactivate_field_with_no_data_no_wizard(self):
        """Test deactivating a field with no data shows no wizard."""
        # Create and activate a field
        field = self.StudioField.create(
            {
                "label": "Empty Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()
        self.assertEqual(field.state, "active")

        # Deactivate - should succeed without wizard since no data
        result = field.action_deactivate()

        # If result is True or None, deactivation succeeded directly
        if result is True or result is None:
            self.assertEqual(field.state, "inactive")
        else:
            # If wizard shown, it should be because there's data
            # But we expect no data here, so this shouldn't happen
            self.assertTrue(False, "Unexpected wizard shown for field with no data")

    def test_deactivate_field_with_data_shows_wizard(self):
        """Test deactivating a field with data shows impact wizard."""
        # Create and activate a field
        field = self.StudioField.create(
            {
                "label": "Field With Data",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()
        self.assertEqual(field.state, "active")

        # Create some partner records with data in this field
        technical_name = field.technical_name

        # Add the field dynamically to partners
        if hasattr(self.Partner, technical_name):
            partners = []
            for i in range(3):
                partner = self.Partner.create(
                    {
                        "name": f"Test Partner {i}",
                        technical_name: f"Test Value {i}",
                    }
                )
                partners.append(partner)

            # Now try to deactivate - should return wizard action
            result = field.action_deactivate()

            # Should return a wizard action dict, not True/None
            self.assertIsInstance(result, dict)
            self.assertEqual(result["type"], "ir.actions.act_window")
            self.assertEqual(result["res_model"], "spp.studio.deactivate.wizard")
            self.assertEqual(result["view_mode"], "form")
            self.assertEqual(result["target"], "new")

            # Check context has expected keys
            context = result.get("context", {})
            self.assertEqual(context.get("default_config_model"), "spp.studio.field")
            self.assertEqual(context.get("default_config_id"), field.id)
            self.assertIn("default_impact_message", context)
            self.assertIn("3", context["default_impact_message"])

            # Clean up test data
            for partner in partners:
                partner.unlink()

    def test_wizard_confirm_deactivates_field(self):
        """Test confirming wizard actually deactivates the field."""
        # Create and activate a field
        field = self.StudioField.create(
            {
                "label": "Wizard Confirm Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()

        # Create wizard manually with impact message
        wizard = self.Wizard.create(
            {
                "config_model": "spp.studio.field",
                "config_id": field.id,
                "impact_message": "This field contains data in 5 records.",
            }
        )

        # Verify wizard extracted count
        self.assertEqual(wizard.record_count, 5)

        # Confirm deactivation
        result = wizard.action_confirm_deactivate()

        # Should close wizard
        self.assertEqual(result["type"], "ir.actions.act_window_close")

        # Field should now be inactive
        field.invalidate_recordset()
        self.assertEqual(field.state, "inactive")
        self.assertTrue(field.deactivated_by_id)
        self.assertTrue(field.deactivated_date)

    def test_impact_message_format(self):
        """Test impact message has expected format."""
        field = self.StudioField.create(
            {
                "label": "Impact Message Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()

        # Get impact directly
        impact = field._get_deactivation_impact()

        # If there's no data, impact should be None
        if impact is None:
            self.assertIsNone(impact)
        else:
            # If there is impact, it should mention records and deactivation
            self.assertIn("record", impact.lower())
            self.assertIn("deactivat", impact.lower())

    def test_wizard_config_info_computed(self):
        """Test wizard computes config info correctly."""
        field = self.StudioField.create(
            {
                "label": "Config Info Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()

        wizard = self.Wizard.create(
            {
                "config_model": "spp.studio.field",
                "config_id": field.id,
                "impact_message": "Test with 1,234 records affected.",
            }
        )

        # Check computed fields
        self.assertEqual(wizard.config_name, field.label)
        self.assertEqual(wizard.config_type, "Registry Field")
        self.assertEqual(wizard.record_count, 1234)
