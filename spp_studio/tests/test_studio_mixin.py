"""Tests for Studio lifecycle mixin."""

from odoo.tests.common import TransactionCase


class TestStudioMixin(TransactionCase):
    """Test cases for spp.studio.mixin lifecycle management.

    Tests the mixin through a concrete model (spp.studio.field) that inherits from it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Use spp.studio.field as a concrete model that inherits from the mixin
        cls.StudioField = cls.env["spp.studio.field"]

    def test_mixin_inheritance(self):
        """Test that the mixin methods are available on inheriting model."""
        # Check that the model has the mixin's methods
        self.assertTrue(hasattr(self.StudioField, "action_activate"))
        self.assertTrue(hasattr(self.StudioField, "action_deactivate"))
        self.assertTrue(hasattr(self.StudioField, "action_reactivate"))

    def test_state_field_definition(self):
        """Test state field has correct selection values."""
        state_field = self.StudioField._fields["state"]
        selection = state_field.selection
        states = [s[0] for s in selection]
        self.assertIn("draft", states)
        self.assertIn("active", states)
        self.assertIn("inactive", states)

    def test_audit_fields_defined(self):
        """Test audit fields are properly defined on inheriting model."""
        fields = self.StudioField._fields
        self.assertIn("created_by_id", fields)
        self.assertIn("created_date", fields)
        self.assertIn("activated_by_id", fields)
        self.assertIn("activated_date", fields)
        self.assertIn("deactivated_by_id", fields)
        self.assertIn("deactivated_date", fields)

