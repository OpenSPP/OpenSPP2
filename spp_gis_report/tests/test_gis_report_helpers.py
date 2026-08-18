# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.gis.report helper methods: threshold calculators, refresh
compute, the member-expansion constraint, and view/refresh actions."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import GISReportTestBase


@tagged("post_install", "-at_install")
class TestGisReportHelpers(GISReportTestBase):
    """Cover quantile/jenks calculators, constraint, compute, and actions."""

    def test_calculate_quantiles(self):
        """Quantile breakpoints span the data and have num_buckets + 1 entries."""
        report = self.create_test_report()
        self.assertEqual(report._calculate_quantiles([], 4), [0, 1])
        breaks = report._calculate_quantiles([1, 2, 3, 4, 5], 4)
        self.assertEqual(len(breaks), 5)
        self.assertEqual(breaks[0], 1)
        self.assertEqual(breaks[-1], 5)

    def test_calculate_jenks_breaks_small_dataset(self):
        """When there are no more values than buckets, values are returned as-is."""
        report = self.create_test_report()
        self.assertEqual(report._calculate_jenks_breaks([10, 20], 5), [10, 20, 20])

    def test_calculate_jenks_breaks_with_gaps(self):
        """The largest natural gap becomes a break point."""
        report = self.create_test_report()
        breaks = report._calculate_jenks_breaks([1, 2, 3, 100, 101, 102], 2)
        self.assertEqual(breaks[0], 1)
        self.assertEqual(breaks[-1], 102)
        self.assertIn(100, breaks)

    def test_compute_next_refresh_without_cron(self):
        """A report with no scheduling cron has no next refresh time."""
        report = self.create_test_report()
        self.assertFalse(report.next_refresh)

    def test_check_member_expansion_rejects_non_partner_source(self):
        """member_expansion='expand' is only valid for res.partner sources."""
        area_model = self.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        with self.assertRaises(ValidationError):
            self.create_test_report(source_model_id=area_model.id, member_expansion="expand")

    def test_check_member_expansion_allows_partner_source(self):
        """member_expansion='expand' is accepted for a res.partner source."""
        report = self.create_test_report(member_expansion="expand")
        self.assertEqual(report.member_expansion, "expand")

    def test_action_view_data(self):
        """The data action targets this report's data records."""
        report = self.create_test_report()
        action = report.action_view_data()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.gis.report.data")
        self.assertEqual(action["domain"], [("report_id", "=", report.id)])

    def test_action_view_map(self):
        """The map action opens the GIS view, or falls back to the data view."""
        report = self.create_test_report()
        action = report.action_view_map()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertIn(action["res_model"], ("spp.area", "spp.gis.report.data"))

    def test_action_refresh_now(self):
        """Refreshing recomputes data and stamps last_refresh."""
        report = self.create_test_report()
        report.action_refresh_now()
        self.assertTrue(report.last_refresh)
