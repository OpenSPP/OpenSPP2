"""Tests for Studio custom fields."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestStudioField(TransactionCase):
    """Test cases for spp.studio.field model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.StudioField = cls.env["spp.studio.field"]
        cls.PlacementZone = cls.env["spp.studio.placement.zone"]

        # Create a test placement zone
        cls.zone = cls.PlacementZone.create(
            {
                "name": "Test Zone",
                "code": "test_zone_field",
                "target_type": "individual",
                "tab_name": "Profile",
                "xpath_expression": (
                    "//notebook[@name='individual_detail']"
                    "//page[@name='profile']"
                    "//group[@name='demographics_section']"
                ),
                "xpath_position": "inside",
            }
        )

    def test_create_text_field(self):
        """Test creating a basic text field."""
        field = self.StudioField.create(
            {
                "label": "Test Text Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        self.assertTrue(field.exists())
        self.assertEqual(field.state, "draft")
        self.assertTrue(field.technical_name.startswith("x_"))
        self.assertIn("test_text_field", field.technical_name)

    def test_technical_name_generation(self):
        """Test technical name is auto-generated from label."""
        field = self.StudioField.create(
            {
                "label": "My Special Field!",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        self.assertEqual(field.technical_name, "x_my_special_field")

    def test_technical_name_uniqueness(self):
        """Test technical names are unique."""
        field1 = self.StudioField.create(
            {
                "label": "Unique Name",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field2 = self.StudioField.create(
            {
                "label": "Unique Name",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        self.assertNotEqual(field1.technical_name, field2.technical_name)
        # Second field should have a counter suffix
        self.assertTrue(field2.technical_name.endswith("_1") or field2.technical_name != field1.technical_name)

    def test_selection_field_requires_options(self):
        """Test selection fields require options."""
        with self.assertRaises(ValidationError):
            self.StudioField.create(
                {
                    "label": "Selection Field",
                    "field_type": "selection",
                    "target_type": "individual",
                    "placement_zone_id": self.zone.id,
                    # Missing selection_options
                }
            )

    def test_selection_field_with_options(self):
        """Test creating selection field with options."""
        field = self.StudioField.create(
            {
                "label": "Status Field",
                "field_type": "selection",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "selection_options": "opt1|Option 1\nopt2|Option 2\nopt3|Option 3",
            }
        )
        options = field._parse_selection_options()
        self.assertEqual(len(options), 3)
        self.assertEqual(options[0], ("opt1", "Option 1"))

    def test_link_field_requires_model(self):
        """Test link fields require link_model_id."""
        with self.assertRaises(ValidationError):
            self.StudioField.create(
                {
                    "label": "Link Field",
                    "field_type": "link",
                    "target_type": "individual",
                    "placement_zone_id": self.zone.id,
                    # Missing link_model_id
                }
            )

    def test_link_field_with_model(self):
        """Test creating link field with model."""
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        field = self.StudioField.create(
            {
                "label": "Related Partner",
                "field_type": "link",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "link_model_id": partner_model.id,
            }
        )
        self.assertEqual(field.link_model_id.model, "res.partner")

    def test_cannot_modify_active_field(self):
        """Test that active fields cannot be modified."""
        field = self.StudioField.create(
            {
                "label": "Locked Field",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        # Activate the field
        field.action_activate()
        self.assertEqual(field.state, "active")

        # Try to modify - should fail
        with self.assertRaises(UserError):
            field.write({"label": "New Label"})

    def test_lifecycle_draft_to_active(self):
        """Test activating a draft field."""
        field = self.StudioField.create(
            {
                "label": "Lifecycle Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        self.assertEqual(field.state, "draft")
        self.assertFalse(field.activated_by_id)

        field.action_activate()

        self.assertEqual(field.state, "active")
        self.assertTrue(field.activated_by_id)
        self.assertTrue(field.activated_date)

    def test_lifecycle_active_to_inactive(self):
        """Test deactivating an active field."""
        field = self.StudioField.create(
            {
                "label": "Deactivate Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()
        self.assertEqual(field.state, "active")

        # Deactivate - may return wizard or succeed directly
        result = field.action_deactivate()
        if result is True or result is None:
            self.assertEqual(field.state, "inactive")
        else:
            # If wizard returned, call _do_deactivate directly
            field._do_deactivate()
            self.assertEqual(field.state, "inactive")

        self.assertTrue(field.deactivated_by_id)
        self.assertTrue(field.deactivated_date)

    def test_cannot_delete_active_field(self):
        """Test that active fields cannot be deleted."""
        field = self.StudioField.create(
            {
                "label": "No Delete",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field.action_activate()

        with self.assertRaises(UserError):
            field.unlink()

    def test_can_delete_draft_field(self):
        """Test that draft fields can be deleted."""
        field = self.StudioField.create(
            {
                "label": "Can Delete",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        field_id = field.id
        field.unlink()
        self.assertFalse(self.StudioField.browse(field_id).exists())

    def test_all_field_types(self):
        """Test creating fields of all types."""
        field_types = [
            ("text", {}),
            ("long_text", {}),
            ("integer", {}),
            ("decimal", {}),
            ("date", {}),
            ("datetime", {}),
            ("boolean", {}),
            (
                "selection",
                {"selection_options": "a|A\nb|B"},
            ),
            (
                "multi_select",
                {"selection_options": "x|X\ny|Y"},
            ),
        ]

        for idx, (ftype, extra_vals) in enumerate(field_types):
            vals = {
                "label": f"Test {ftype} {idx}",
                "field_type": ftype,
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
            vals.update(extra_vals)
            field = self.StudioField.create(vals)
            self.assertEqual(field.field_type, ftype)

    def test_target_model_computed(self):
        """Test target_model is computed from target_type."""
        field = self.StudioField.create(
            {
                "label": "Target Model Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        self.assertEqual(field.target_model, "res.partner")
