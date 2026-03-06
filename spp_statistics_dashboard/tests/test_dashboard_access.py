# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for dashboard access rights with viewer/manager user contexts."""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestDashboardAccess(TransactionCase):
    """Test ACLs with dashboard viewer vs. manager user contexts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Access Test Category",
                "code": "access_test_cat",
            }
        )

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "access_test_var",
                "cel_accessor": "access_test_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )

        cls.statistic = cls.env["spp.statistic"].create(
            {
                "name": "access_test_stat",
                "label": "Access Test Stat",
                "variable_id": cls.cel_variable.id,
                "category_id": cls.category.id,
                "is_published_dashboard": True,
            }
        )

        cls.dashboard_data = cls.env["spp.dashboard.data"].create(
            {
                "statistic_id": cls.statistic.id,
                "value": 42.0,
                "value_display": "42",
                "label": "Access Test Stat",
            }
        )

        # Create test users
        viewer_group = cls.env.ref("spp_statistics_dashboard.group_dashboard_viewer")
        cls.viewer_user = cls.env["res.users"].create(
            {
                "name": "Dashboard Viewer",
                "login": "test_dashboard_viewer",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(viewer_group.id),
                ],
            }
        )

        manager_group = cls.env.ref("spp_statistics_dashboard.group_dashboard_manager")
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Dashboard Manager",
                "login": "test_dashboard_manager",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(manager_group.id),
                ],
            }
        )

        # Create a user with no dashboard group
        cls.no_access_user = cls.env["res.users"].create(
            {
                "name": "No Access User",
                "login": "test_no_dashboard_access",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                ],
            }
        )

    def test_viewer_can_read(self):
        """Test that viewer can read dashboard data."""
        data = self.dashboard_data.with_user(self.viewer_user)
        data.read(["value", "value_display", "label"])

    def test_viewer_cannot_write(self):
        """Test that viewer cannot write dashboard data."""
        data = self.dashboard_data.with_user(self.viewer_user)
        with self.assertRaises(AccessError):
            data.write({"value": 99.0})

    def test_viewer_cannot_create(self):
        """Test that viewer cannot create dashboard data."""
        DashData = self.env["spp.dashboard.data"].with_user(self.viewer_user)
        with self.assertRaises(AccessError):
            DashData.create(
                {
                    "statistic_id": self.statistic.id,
                    "value": 1.0,
                    "value_display": "1",
                    "label": "Forbidden",
                }
            )

    def test_viewer_cannot_unlink(self):
        """Test that viewer cannot delete dashboard data."""
        data = self.dashboard_data.with_user(self.viewer_user)
        with self.assertRaises(AccessError):
            data.unlink()

    def test_manager_can_read(self):
        """Test that manager can read dashboard data."""
        data = self.dashboard_data.with_user(self.manager_user)
        data.read(["value", "value_display", "label"])

    def test_manager_can_write(self):
        """Test that manager can write dashboard data."""
        data = self.dashboard_data.with_user(self.manager_user)
        data.write({"value": 99.0})
        self.assertEqual(data.value, 99.0)

    def test_manager_can_create(self):
        """Test that manager can create dashboard data."""
        # Create a separate statistic to avoid unique constraint with setUpClass data
        cel_var = self.env["spp.cel.variable"].create(
            {
                "name": "access_create_var",
                "cel_accessor": "access_create_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )
        stat = self.env["spp.statistic"].create(
            {
                "name": "access_create_stat",
                "label": "Access Create Stat",
                "variable_id": cel_var.id,
                "is_published_dashboard": True,
            }
        )

        DashData = self.env["spp.dashboard.data"].with_user(self.manager_user)
        data = DashData.create(
            {
                "statistic_id": stat.id,
                "value": 55.0,
                "value_display": "55",
                "label": "Manager Created",
            }
        )
        self.assertTrue(data.exists())

    def test_manager_can_unlink(self):
        """Test that manager can delete dashboard data."""
        data = self.env["spp.dashboard.data"].create(
            {
                "statistic_id": self.statistic.id,
                "value": 77.0,
                "value_display": "77",
                "label": "To Delete",
                "area_id": self.env["spp.area"]
                .create(
                    {
                        "draft_name": "Delete Test Area",
                        "code": "delete_test_area_dash",
                    }
                )
                .id,
            }
        )
        data_as_manager = data.with_user(self.manager_user)
        data_as_manager.unlink()

    def test_no_access_user_cannot_read(self):
        """Test that user without dashboard group cannot read."""
        data = self.dashboard_data.with_user(self.no_access_user)
        with self.assertRaises(AccessError):
            data.read(["value"])

    def test_manager_implies_viewer(self):
        """Test that manager group implies viewer group (read access)."""
        manager_group = self.env.ref("spp_statistics_dashboard.group_dashboard_manager")
        viewer_group = self.env.ref("spp_statistics_dashboard.group_dashboard_viewer")
        read_group = self.env.ref("spp_statistics_dashboard.group_dashboard_read")
        manage_group = self.env.ref("spp_statistics_dashboard.group_dashboard_manage")

        self.assertIn(viewer_group, manager_group.implied_ids)
        self.assertIn(manage_group, manager_group.implied_ids)
        self.assertIn(read_group, viewer_group.implied_ids)

    def test_viewer_has_read_group(self):
        """Test that viewer user has the technical read group."""
        self.assertTrue(self.viewer_user.has_group("spp_statistics_dashboard.group_dashboard_read"))

    def test_manager_has_manage_group(self):
        """Test that manager user has the technical manage group."""
        self.assertTrue(self.manager_user.has_group("spp_statistics_dashboard.group_dashboard_manage"))
