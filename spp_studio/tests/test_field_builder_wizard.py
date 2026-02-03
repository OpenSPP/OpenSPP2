"""Tests for Field Builder Wizard."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestFieldBuilderWizard(TransactionCase):
    """Test cases for spp.studio.field.builder.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Wizard = cls.env["spp.studio.field.builder.wizard"]
        cls.PlacementZone = cls.env["spp.studio.placement.zone"]

        # Create a test placement zone with valid xpath from actual form view
        cls.zone = cls.PlacementZone.create(
            {
                "name": "Test Zone Wizard",
                "code": "test_zone_wizard",
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

    def test_wizard_step_navigation(self):
        """Test wizard step navigation."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                "label": "Test Field",
            }
        )
        self.assertEqual(wizard.step, "basic")

        # Move to config
        wizard.action_next()
        self.assertEqual(wizard.step, "config")

        # Add required config
        wizard.placement_zone_id = self.zone.id

        # Move to review
        wizard.action_next()
        self.assertEqual(wizard.step, "review")

        # Go back to config
        wizard.action_previous()
        self.assertEqual(wizard.step, "config")

        # Go back to basic
        wizard.action_previous()
        self.assertEqual(wizard.step, "basic")

    def test_wizard_requires_label(self):
        """Test wizard requires label before next step."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                # No label
            }
        )
        with self.assertRaises(ValidationError):
            wizard.action_next()

    def test_wizard_requires_placement_zone(self):
        """Test wizard requires placement zone before review."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                "label": "Test Field",
            }
        )
        wizard.action_next()
        self.assertEqual(wizard.step, "config")

        # Try to proceed without placement zone
        with self.assertRaises(ValidationError):
            wizard.action_next()

    def test_wizard_requires_selection_options(self):
        """Test wizard requires selection options for selection fields."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "selection",
                "label": "Selection Test",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id

        # Try to proceed without options
        with self.assertRaises(ValidationError):
            wizard.action_next()

    def test_wizard_requires_link_model(self):
        """Test wizard requires link model for link fields."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "link",
                "label": "Link Test",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id

        # Try to proceed without link model
        with self.assertRaises(ValidationError):
            wizard.action_next()

    def test_wizard_creates_field(self):
        """Test wizard creates and activates a studio field by default."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                "label": "Created by Wizard",
                "help_text": "Help text here",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id
        wizard.is_required = True
        wizard.action_next()

        # Create and activate the field
        result = wizard.action_create_field()

        # Wizard should simply close in the default path
        self.assertEqual(result["type"], "ir.actions.act_window_close")

        # Verify field was created and activated
        field = self.env["spp.studio.field"].search([("label", "=", "Created by Wizard")], limit=1)
        self.assertTrue(field.exists())
        self.assertEqual(field.help_text, "Help text here")
        self.assertEqual(field.state, "active")
        self.assertTrue(field.is_required)

    def test_wizard_can_create_draft_field(self):
        """Test wizard can create a draft field without activating it."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                "label": "Draft by Wizard",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id
        wizard.create_as_draft = True
        wizard.action_next()

        result = wizard.action_create_field()

        # When creating as draft, wizard opens the field form
        self.assertEqual(result["res_model"], "spp.studio.field")

        field = self.env["spp.studio.field"].search([("label", "=", "Draft by Wizard")], limit=1)
        self.assertTrue(field.exists())
        self.assertEqual(field.state, "draft")

    def test_wizard_creates_selection_field(self):
        """Test wizard creates selection field with options."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "selection",
                "label": "Status",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id
        wizard.selection_options = "pending|Pending\napproved|Approved\nrejected|Rejected"
        wizard.action_next()

        wizard.action_create_field()
        field = self.env["spp.studio.field"].search([("label", "=", "Status")], limit=1)

        self.assertEqual(field.field_type, "selection")
        self.assertIn("pending|Pending", field.selection_options)

    def test_wizard_creates_link_field(self):
        """Test wizard creates link field with model."""
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "link",
                "label": "Related Contact",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id
        wizard.link_model_id = partner_model.id
        wizard.link_domain = "[('is_company', '=', True)]"
        wizard.action_next()

        wizard.action_create_field()
        field = self.env["spp.studio.field"].search([("label", "=", "Related Contact")], limit=1)

        self.assertEqual(field.field_type, "link")
        self.assertEqual(field.link_model_id, partner_model)
        self.assertEqual(field.link_domain, "[('is_company', '=', True)]")

    def test_wizard_creates_conditional_field(self):
        """Test wizard creates field with conditional visibility."""
        # Get a field to use for visibility condition
        name_field = self.env["ir.model.fields"].search([("model", "=", "res.partner"), ("name", "=", "name")], limit=1)

        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "text",
                "label": "Conditional Field",
            }
        )
        wizard.action_next()
        wizard.placement_zone_id = self.zone.id
        wizard.visibility_condition = "conditional"
        wizard.visibility_field_id = name_field.id
        wizard.visibility_operator = "set"
        wizard.action_next()

        wizard.action_create_field()
        field = self.env["spp.studio.field"].search([("label", "=", "Conditional Field")], limit=1)

        self.assertEqual(field.visibility_condition, "conditional")
        self.assertEqual(field.visibility_field_id, name_field)
        self.assertEqual(field.visibility_operator, "set")

    def test_preview_computed_fields(self):
        """Test preview fields are computed."""
        wizard = self.Wizard.create(
            {
                "target_type": "individual",
                "field_type": "integer",
                "label": "Age in Years",
            }
        )
        self.assertEqual(wizard.preview_technical_name, "x_age_in_years")
        self.assertEqual(wizard.preview_odoo_type, "Integer")

        wizard.field_type = "boolean"
        self.assertEqual(wizard.preview_odoo_type, "Boolean")
