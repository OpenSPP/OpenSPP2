# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration tests for dashboard refresh using real aggregation pipeline.

These tests call through the real aggregation service (no mocks) to verify
that the dashboard correctly computes and displays statistics.
"""

import logging

from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestDashboardIntegration(TransactionCase):
    """Integration tests that exercise the real aggregation pipeline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Integration Test",
                "code": "integration_test",
            }
        )

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "integ_test_total",
                "cel_accessor": "integ_test_total",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )

        cls.statistic = cls.env["spp.statistic"].create(
            {
                "name": "integ_test_stat",
                "label": "Integration Total",
                "variable_id": cls.cel_variable.id,
                "category_id": cls.category.id,
                "format": "count",
                "unit": "people",
                "is_published_dashboard": True,
            }
        )

        # Create real registrants (individuals)
        cls.registrants = cls.env["res.partner"].create(
            [
                {
                    "name": f"Integration Test Person {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
                for i in range(20)
            ]
        )

    def test_scope_resolution_system_wide(self):
        """Test that system-wide scope resolves to actual registrants."""
        DashData = self.env["spp.dashboard.data"]
        scope = DashData._build_scope(False, False)

        self.assertEqual(scope["scope_type"], "explicit")

        # The explicit_partner_ids should contain our registrants
        partner_ids = scope["explicit_partner_ids"]
        self.assertGreaterEqual(
            len(partner_ids),
            len(self.registrants),
            f"Expected at least {len(self.registrants)} registrants, got {len(partner_ids)}",
        )

        # Our specific registrants should be in the result
        for reg in self.registrants:
            self.assertIn(reg.id, partner_ids)

    def test_aggregation_service_returns_values(self):
        """Test that compute_aggregation returns non-suppressed values for large populations."""
        DashData = self.env["spp.dashboard.data"]
        scope = DashData._build_scope(False, False)

        result = self.env["spp.aggregation.service"].compute_aggregation(
            scope=scope,
            statistics=[self.statistic.name],
            context="dashboard",
        )

        # total_count should reflect actual registrants
        self.assertGreaterEqual(
            result["total_count"],
            len(self.registrants),
            f"Expected total_count >= {len(self.registrants)}, got {result['total_count']}",
        )

        # The statistic should be in results
        self.assertIn(self.statistic.name, result["statistics"])

        stat_data = result["statistics"][self.statistic.name]
        _logger.info(
            "Aggregation result: value=%s, suppressed=%s, total_count=%s",
            stat_data.get("value"),
            stat_data.get("suppressed"),
            result["total_count"],
        )

        # With 20+ registrants, the value should NOT be suppressed (default k=5)
        self.assertFalse(
            stat_data.get("suppressed"),
            f"Value should not be suppressed with {result['total_count']} registrants. Got: {stat_data}",
        )

    def test_refresh_produces_real_values(self):
        """Test end-to-end: refresh creates dashboard rows with real computed values."""
        DashData = self.env["spp.dashboard.data"]

        # Run refresh (no mocks)
        DashData._refresh_statistic(self.statistic.id, [])

        # Check the system-wide row
        data = DashData.search(
            [
                ("statistic_id", "=", self.statistic.id),
                ("area_id", "=", False),
                ("program_id", "=", False),
            ]
        )
        self.assertEqual(len(data), 1, "Expected exactly one system-wide row")

        _logger.info(
            "Dashboard row: value=%s, value_display=%s, is_suppressed=%s, underlying_count=%s",
            data.value,
            data.value_display,
            data.is_suppressed,
            data.underlying_count,
        )

        # With 20+ registrants, the value should NOT be suppressed
        self.assertFalse(
            data.is_suppressed,
            f"Dashboard value should not be suppressed. "
            f"value_display={data.value_display}, underlying_count={data.underlying_count}",
        )

        # The numeric value should be > 0
        self.assertGreater(
            data.value,
            0,
            f"Dashboard value should be > 0, got {data.value}",
        )

        # The display value should be a formatted number, not a suppression marker
        self.assertNotIn("<", data.value_display, f"Display value looks suppressed: {data.value_display}")
        self.assertNotEqual(data.value_display, "*", f"Display value looks suppressed: {data.value_display}")
