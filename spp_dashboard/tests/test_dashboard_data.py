# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dashboard.data model creation, constraints, and formatting."""

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestDashboardData(TransactionCase):
    """Test dashboard data model and constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Demographics",
                "code": "demographics",
            }
        )

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_dashboard_var",
                "cel_accessor": "test_dashboard_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )

        cls.statistic = cls.env["spp.statistic"].create(
            {
                "name": "test_stat_dashboard",
                "label": "Test Stat",
                "variable_id": cls.cel_variable.id,
                "category_id": cls.category.id,
                "format": "count",
                "unit": "people",
                "is_published_dashboard": True,
            }
        )

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area",
                "code": "test_area_dash",
            }
        )

    def test_create_dashboard_data(self):
        """Test creating a dashboard data record."""
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "value": 42.0,
                "value_display": "42",
                "label": "Test Stat",
            }
        )

        self.assertEqual(data.statistic_name, "test_stat_dashboard")
        self.assertEqual(data.category_id, self.category)
        self.assertEqual(data.category_code, "demographics")
        self.assertEqual(data.value, 42.0)
        self.assertEqual(data.value_display, "42")
        self.assertEqual(data.format, "count")
        self.assertEqual(data.unit, "people")
        self.assertFalse(data.is_suppressed)

    def test_create_with_area(self):
        """Test creating dashboard data with area scope."""
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "area_id": self.area.id,
                "value": 10.0,
                "value_display": "10",
                "label": "Test Stat",
            }
        )

        # area_name is computed from draft_name + code
        self.assertIn("Test Area", data.area_name)
        # Root area has area_level=0
        self.assertEqual(data.area_level, 0)

    def test_unique_constraint(self):
        """Test SQL unique constraint on (statistic_id, area_id, program_id)."""
        self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "area_id": self.area.id,
                "value": 10.0,
                "value_display": "10",
                "label": "Test Stat",
            }
        )

        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.dashboard.data"].create(
                {
                    "statistic_id": self.statistic.id,
                    "area_id": self.area.id,
                    "value": 20.0,
                    "value_display": "20",
                    "label": "Test Stat",
                }
            )

    def test_cascade_delete_statistic(self):
        """Test that deleting a statistic cascades to dashboard data."""
        cel_var = self.env["spp.cel.variable"].create(
            {
                "name": "cascade_test_var",
                "cel_accessor": "cascade_test_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )
        stat = self.env["spp.statistic"].create(
            {
                "name": "cascade_test_stat",
                "label": "Cascade Test",
                "variable_id": cel_var.id,
                "is_published_dashboard": True,
            }
        )
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": stat.id,
                "value": 5.0,
                "value_display": "5",
                "label": "Cascade Test",
            }
        )
        data_id = data.id

        stat.unlink()
        self.assertFalse(self.env["spp.dashboard.data"].browse(data_id).exists())

    def test_cascade_delete_area(self):
        """Test that deleting an area cascades to dashboard data."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Cascade Area",
                "code": "cascade_area_dash",
            }
        )
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "area_id": area.id,
                "value": 7.0,
                "value_display": "7",
                "label": "Test",
            }
        )
        data_id = data.id

        area.unlink()
        self.assertFalse(self.env["spp.dashboard.data"].browse(data_id).exists())

    def test_format_value_count(self):
        """Test value formatting for count format."""
        DashData = self.env["spp.dashboard.data"]
        result = DashData._format_value(1234, self.statistic)
        self.assertEqual(result, "1,234")

    def test_format_value_percent(self):
        """Test value formatting for percent format."""
        DashData = self.env["spp.dashboard.data"]
        stat = self.env["spp.statistic"].create(
            {
                "name": "pct_stat",
                "label": "Pct Stat",
                "variable_id": self.cel_variable.id,
                "format": "percent",
                "decimal_places": 1,
            }
        )
        result = DashData._format_value(75.5, stat)
        self.assertEqual(result, "75.5%")

    def test_format_value_none(self):
        """Test value formatting for None value."""
        DashData = self.env["spp.dashboard.data"]
        result = DashData._format_value(None, self.statistic)
        self.assertEqual(result, "")

    def test_related_fields_stored(self):
        """Test that related fields are stored correctly for search/export."""
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "value": 1.0,
                "value_display": "1",
                "label": "Test",
            }
        )

        # Verify stored related fields are searchable
        found = self.env["spp.dashboard.data"].search(
            [
                ("statistic_name", "=", "test_stat_dashboard"),
            ]
        )
        self.assertIn(data, found)

        found = self.env["spp.dashboard.data"].search(
            [
                ("category_code", "=", "demographics"),
            ]
        )
        self.assertIn(data, found)


class TestDashboardViews(TransactionCase):
    """Test that view definitions load correctly."""

    def test_kanban_view_loads(self):
        """Test kanban view can be loaded without error."""
        view = self.env.ref("spp_dashboard.spp_dashboard_data_view_kanban")
        result = self.env["spp.dashboard.data"].get_view(view.id, view_type="kanban")
        self.assertIn("arch", result)

    def test_list_view_loads(self):
        """Test list view can be loaded without error."""
        view = self.env.ref("spp_dashboard.spp_dashboard_data_view_list")
        result = self.env["spp.dashboard.data"].get_view(view.id, view_type="list")
        self.assertIn("arch", result)

    def test_search_view_loads(self):
        """Test search view can be loaded without error."""
        view = self.env.ref("spp_dashboard.spp_dashboard_data_view_search")
        result = self.env["spp.dashboard.data"].get_view(view.id, view_type="search")
        self.assertIn("arch", result)

    def test_pivot_view_loads(self):
        """Test pivot view can be loaded without error."""
        view = self.env.ref("spp_dashboard.spp_dashboard_data_view_pivot")
        result = self.env["spp.dashboard.data"].get_view(view.id, view_type="pivot")
        self.assertIn("arch", result)

    def test_graph_view_loads(self):
        """Test graph view can be loaded without error."""
        view = self.env.ref("spp_dashboard.spp_dashboard_data_view_graph")
        result = self.env["spp.dashboard.data"].get_view(view.id, view_type="graph")
        self.assertIn("arch", result)

    def test_action_window_exists(self):
        """Test action window record exists with correct settings."""
        action = self.env.ref("spp_dashboard.action_dashboard_data")
        self.assertEqual(action.res_model, "spp.dashboard.data")
        self.assertEqual(action.path, "statistics-dashboard")
        self.assertIn("search_default_system_wide", action.context)

    def test_server_action_exists(self):
        """Test server action for refresh exists."""
        action = self.env.ref("spp_dashboard.action_refresh_dashboard_data")
        self.assertEqual(action.state, "code")
