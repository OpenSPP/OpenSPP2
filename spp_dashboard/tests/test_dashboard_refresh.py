# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for dashboard refresh logic, error handling, and stale cleanup."""

from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestDashboardRefresh(TransactionCase):
    """Test refresh logic for dashboard data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Test Category",
                "code": "test_refresh_cat",
            }
        )

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "refresh_test_var",
                "cel_accessor": "refresh_test_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )

        cls.statistic = cls.env["spp.statistic"].create(
            {
                "name": "refresh_test_stat",
                "label": "Refresh Test Stat",
                "variable_id": cls.cel_variable.id,
                "category_id": cls.category.id,
                "format": "count",
                "unit": "people",
                "minimum_count": 5,
                "suppression_display": "less_than",
                "is_published_dashboard": True,
            }
        )

        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Refresh Area",
                "code": "refresh_area_dash",
            }
        )

    def _mock_aggregation_result(self, value=100, suppressed=False, total_count=50):
        """Build a mock aggregation result dict."""
        return {
            "total_count": total_count,
            "statistics": {
                "refresh_test_stat": {
                    "value": value,
                    "suppressed": suppressed,
                },
            },
            "from_cache": False,
            "computed_at": "2026-01-01T00:00:00",
            "access_level": "aggregate",
        }

    def test_refresh_statistic_creates_data(self):
        """Test that _refresh_statistic creates dashboard data rows."""
        DashData = self.env["spp.dashboard.data"]
        mock_result = self._mock_aggregation_result(value=100, total_count=50)

        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [])

        # Should create one row: system-wide, no program
        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data.value, 100.0)
        self.assertEqual(data.value_display, "100")
        self.assertFalse(data.is_suppressed)
        self.assertEqual(data.underlying_count, 50)
        self.assertTrue(data.refreshed_at)

    def test_refresh_statistic_with_area(self):
        """Test refresh creates rows for specified areas."""
        DashData = self.env["spp.dashboard.data"]
        mock_result = self._mock_aggregation_result(value=25, total_count=25)

        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [self.area.id])

        # Should create 2 rows: system-wide + one area
        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
            ]
        )
        self.assertEqual(len(data), 2)

        area_data = data.filtered(lambda d: d.area_id == self.area)
        self.assertEqual(len(area_data), 1)
        self.assertEqual(area_data.value, 25.0)

    def test_refresh_statistic_upserts(self):
        """Test that refresh updates existing rows instead of duplicating."""
        DashData = self.env["spp.dashboard.data"]

        # First refresh
        mock_result = self._mock_aggregation_result(value=100)
        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [])

        # Second refresh with different value
        mock_result = self._mock_aggregation_result(value=200)
        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [])

        # Should still be one row, with updated value
        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data.value, 200.0)

    def test_refresh_statistic_suppressed_value(self):
        """Test that suppressed values are handled correctly."""
        DashData = self.env["spp.dashboard.data"]
        mock_result = self._mock_aggregation_result(value=3, suppressed=True, total_count=3)

        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [])

        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(len(data), 1)
        self.assertTrue(data.is_suppressed)
        # The display value should reflect suppression
        self.assertTrue(data.value_display)

    def test_refresh_statistic_error_isolation(self):
        """Test that one aggregation failure does not abort the entire refresh."""
        DashData = self.env["spp.dashboard.data"]
        call_count = 0

        def mock_compute(self_svc, scope, statistics=None, context=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if scope.get("area_id") == self.area.id:
                raise ValueError("Simulated aggregation error")
            return self._mock_aggregation_result(value=50, total_count=50)

        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            mock_compute,
        ):
            DashData._refresh_statistic(self.statistic.id, [self.area.id])

        # System-wide row should exist despite area failure
        system_wide = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(len(system_wide), 1)
        self.assertEqual(system_wide.value, 50.0)

        # Area row should NOT exist due to error
        area_data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", self.area.id),
            ]
        )
        self.assertEqual(len(area_data), 0)

    def test_refresh_nonexistent_statistic(self):
        """Test refresh with a deleted statistic does not crash."""
        DashData = self.env["spp.dashboard.data"]
        # Use a non-existent ID
        DashData._refresh_statistic(999999, [])
        # Should not raise, just log a warning

    def test_cleanup_stale_data(self):
        """Test that stale data for un-published statistics is cleaned up."""
        DashData = self.env["spp.dashboard.data"]

        # Create an un-published statistic with dashboard data
        unpub_stat = self.env["spp.statistic"].create(
            {
                "name": "unpub_stat",
                "label": "Unpublished Stat",
                "variable_id": self.cel_variable.id,
                "is_published_dashboard": False,
            }
        )
        stale_data = DashData.create(
            {
                "statistic_id": unpub_stat.id,
                "value": 99.0,
                "value_display": "99",
                "label": "Stale",
            }
        )

        # Also create data for the published statistic
        fresh_data = DashData.create(
            {
                "statistic_id": self.statistic.id,
                "value": 10.0,
                "value_display": "10",
                "label": "Fresh",
            }
        )

        published_stats = self.env["spp.statistic"].get_published_for_context("dashboard")
        DashData._cleanup_stale_data(published_stats)

        # Stale data should be deleted
        self.assertFalse(stale_data.exists())
        # Fresh data should remain
        self.assertTrue(fresh_data.exists())

    def test_action_refresh_all_no_stats(self):
        """Test action_refresh_all returns warning when no stats published."""
        # Un-publish all stats temporarily
        self.statistic.is_published_dashboard = False

        DashData = self.env["spp.dashboard.data"]
        result = DashData.action_refresh_all()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "warning")

        # Restore
        self.statistic.is_published_dashboard = True

    def test_action_refresh_all_with_stats(self):
        """Test action_refresh_all returns success notification."""
        DashData = self.env["spp.dashboard.data"]

        mock_result = self._mock_aggregation_result(value=10)
        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            result = DashData.action_refresh_all()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_get_dashboard_areas_all(self):
        """Test _get_dashboard_areas returns all areas when no param set."""
        DashData = self.env["spp.dashboard.data"]
        areas = DashData._get_dashboard_areas()
        # Should include at least our test area
        self.assertIn(self.area, areas)

    def test_get_dashboard_areas_filtered(self):
        """Test _get_dashboard_areas filters by area_levels system parameter."""
        # Our test area is a root area (area_level=0)
        self.env["ir.config_parameter"].sudo().set_param("spp_dashboard.area_levels", "0")

        DashData = self.env["spp.dashboard.data"]
        areas = DashData._get_dashboard_areas()

        for area in areas:
            self.assertEqual(area.area_level, 0)

        self.assertIn(self.area, areas)

        # Clean up
        self.env["ir.config_parameter"].sudo().set_param("spp_dashboard.area_levels", "")

    def test_get_dashboard_programs(self):
        """Test _get_dashboard_programs returns active programs."""
        DashData = self.env["spp.dashboard.data"]
        programs = DashData._get_dashboard_programs()
        for prog in programs:
            self.assertEqual(prog.state, "active")

    def test_build_scope_system_wide(self):
        """Test _build_scope with no area returns CEL scope for all registrants."""
        DashData = self.env["spp.dashboard.data"]
        scope = DashData._build_scope(False, False)
        self.assertEqual(scope["scope_type"], "cel")
        self.assertEqual(scope["cel_expression"], "true")

    def test_build_scope_with_area(self):
        """Test _build_scope with an area."""
        DashData = self.env["spp.dashboard.data"]
        scope = DashData._build_scope(self.area, False)
        self.assertEqual(scope["scope_type"], "area")
        self.assertEqual(scope["area_id"], self.area.id)
        self.assertTrue(scope["include_child_areas"])

    def test_label_from_context_config(self):
        """Test that label is taken from statistic context config."""
        # Create a context config with a dashboard label override
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.statistic.id,
                "context": "dashboard",
                "label": "Dashboard Custom Label",
            }
        )

        DashData = self.env["spp.dashboard.data"]
        mock_result = self._mock_aggregation_result(value=42, total_count=42)

        with patch.object(
            type(self.env["spp.aggregation.service"]),
            "compute_aggregation",
            return_value=mock_result,
        ):
            DashData._refresh_statistic(self.statistic.id, [])

        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(data.label, "Dashboard Custom Label")
