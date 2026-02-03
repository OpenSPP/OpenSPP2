"""Tests for generic event wizard integration with Studio event types."""

from datetime import date

from odoo.tests.common import TransactionCase


class TestCreateEventWizardStudioIntegration(TransactionCase):
    """Test that generic wizard properly redirects to Studio wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a registrant (individual)
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a Studio event type
        cls.studio_event_type = cls.env["spp.studio.event.type"].create(
            {
                "name": "Test Studio Event",
                "target_type": "individual",
            }
        )

        # Add a field to make it valid for activation
        cls.env["spp.studio.event.field"].create(
            {
                "event_type_id": cls.studio_event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate to create spp.event.type
        cls.studio_event_type.action_activate()
        cls.event_type = cls.studio_event_type.spp_event_type_id

        # Create a regular (non-Studio) event type for comparison
        cls.regular_event_type = cls.env["spp.event.type"].create(
            {
                "name": "Regular Event",
                "code": "regular_event_test",
                "category": "manual",
            }
        )

    def test_event_type_has_studio_reference(self):
        """Test that event type has reverse reference to Studio type."""
        self.assertEqual(
            self.event_type.studio_event_type_ids,
            self.studio_event_type,
        )

    def test_get_active_studio_event_type(self):
        """Test helper method to get active Studio event type."""
        result = self.event_type._get_active_studio_event_type()
        self.assertEqual(result, self.studio_event_type)

    def test_regular_event_type_has_no_studio_reference(self):
        """Test regular event types have no Studio reference."""
        result = self.regular_event_type._get_active_studio_event_type()
        self.assertFalse(result)

    def test_generic_wizard_redirects_to_studio(self):
        """Test that generic wizard redirects when Studio event selected."""
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "event_type_id": self.event_type.id,
                "collection_date": date.today(),
            }
        )

        # Call create_event which should redirect
        result = wizard.create_event()

        # Should return action for Studio wizard with context defaults
        self.assertEqual(result["res_model"], "spp.event.data.entry.wizard")
        self.assertEqual(result["target"], "new")
        # No res_id - wizard is created via context defaults for dynamic field injection
        self.assertFalse(result.get("res_id"))
        # Context should have defaults
        self.assertIn("context", result)
        self.assertEqual(
            result["context"]["default_studio_event_type_id"],
            self.studio_event_type.id,
        )

    def test_generic_wizard_normal_flow_for_non_studio(self):
        """Test that generic wizard works normally for non-Studio types."""
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "event_type_id": self.regular_event_type.id,
                "collection_date": date.today(),
            }
        )

        result = wizard.create_event()

        # Should create event and return to event form
        self.assertEqual(result["res_model"], "spp.event.data")

    def test_studio_wizard_receives_partner_and_date(self):
        """Test that Studio wizard context has correct defaults from generic wizard."""
        test_date = date(2024, 1, 15)

        wizard = self.env["spp.create.event.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "event_type_id": self.event_type.id,
                "collection_date": test_date,
            }
        )

        result = wizard.create_event()

        # Context should have defaults for the Studio wizard
        ctx = result.get("context", {})
        self.assertEqual(ctx.get("default_partner_id"), self.registrant.id)
        self.assertEqual(ctx.get("default_collection_date"), str(test_date))
        self.assertEqual(
            ctx.get("default_studio_event_type_id"),
            self.studio_event_type.id,
        )

    def test_studio_wizard_has_dynamic_fields(self):
        """Test that Studio wizard has dynamic x_evt_* fields when generated view exists."""
        # Create wizard directly with studio_event_type_id
        studio_wizard = self.env["spp.event.data.entry.wizard"].create(
            {
                "studio_event_type_id": self.studio_event_type.id,
                "partner_id": self.registrant.id,
                "collection_date": date.today(),
            }
        )

        # When a generated wizard view exists, field_value_ids should NOT be populated
        # because we use dynamic x_evt_* fields instead
        self.assertTrue(self.studio_event_type.wizard_view_id)

        # Trigger onchange - should NOT populate field_value_ids when wizard_view_id exists
        studio_wizard._onchange_studio_event_type_id()
        self.assertFalse(studio_wizard.field_value_ids)

        # Dynamic fields should exist on the wizard model
        test_field = self.studio_event_type.data_fields[0]
        field_name = f"x_evt_{test_field.technical_name}"
        self.assertIn(field_name, studio_wizard._fields)

    def test_inactive_studio_type_does_not_redirect(self):
        """Test that inactive Studio types don't trigger redirect."""
        # Deactivate the Studio event type
        self.studio_event_type.action_deactivate()

        # Event type still exists but Studio config is inactive
        result = self.event_type._get_active_studio_event_type()
        self.assertFalse(result)

        # Create wizard - should NOT redirect since Studio type is inactive
        wizard = self.env["spp.create.event.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "event_type_id": self.event_type.id,
                "collection_date": date.today(),
            }
        )

        result = wizard.create_event()

        # Should create normal event, not redirect to Studio wizard
        self.assertEqual(result["res_model"], "spp.event.data")

        # Reactivate for other tests
        self.studio_event_type.action_reactivate()
