"""Test cases for Studio Dashboard."""

from odoo.tests import TransactionCase


class TestStudioDashboard(TransactionCase):
    """Test cases for spp.studio.dashboard model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dashboard = cls.env["spp.studio.dashboard"]

    def test_dashboard_creation(self):
        """Test that dashboard can be created."""
        dashboard = self.Dashboard.create({})
        self.assertTrue(dashboard.exists())

    def test_action_open_expressions(self):
        """Test action_open_expressions returns window action."""
        dashboard = self.Dashboard.create({})
        result = dashboard.action_open_expressions()

        # Should return a window action since model exists
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.cel.expression")

    def test_action_open_variables(self):
        """Test action_open_variables returns window action."""
        dashboard = self.Dashboard.create({})
        result = dashboard.action_open_variables()

        # Should return a window action since model exists
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.cel.variable")

    def test_action_manage_registry_fields(self):
        """Test action_manage_registry_fields returns window action."""
        dashboard = self.Dashboard.create({})
        result = dashboard.action_manage_registry_fields()

        # Should return a window action since model exists
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.studio.field")

    def test_action_manage_event_types_not_available(self):
        """Test action_manage_event_types when model doesn't exist."""
        dashboard = self.Dashboard.create({})
        result = dashboard.action_manage_event_types()

        # Should return a notification when model doesn't exist
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("Event Types", result["params"]["title"])

    def test_action_manage_change_request_types_not_available(self):
        """Test action_manage_change_request_types when model doesn't exist."""
        dashboard = self.Dashboard.create({})
        result = dashboard.action_manage_change_request_types()

        # Should return a notification when model doesn't exist
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("Change Requests", result["params"]["title"])
