# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Install / data-load sanity tests for spp_farmer_registry_dashboard.

This is a data-only module — it ships dashboard metric definitions and
spreadsheet dashboards but no Python models or methods. The tests exercise
the install path so CI's per-module coverage matrix records something
against it, and assert that the headline dashboard data records loaded.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSppFarmerRegistryDashboard(TransactionCase):
    """Spot-check that the seed data declared in __manifest__.py loaded."""

    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_farmer_registry_dashboard")], limit=1)
        self.assertTrue(module, "spp_farmer_registry_dashboard not registered")
        self.assertEqual(
            module.state,
            "installed",
            f"spp_farmer_registry_dashboard expected 'installed', got {module.state}",
        )

    def test_dashboard_metric_category_seed_loaded(self):
        """data/dashboard_metrics.xml declares the farmer dashboard category."""
        category = self.env.ref(
            "spp_farmer_registry_dashboard.category_dashboard_farmer",
            raise_if_not_found=False,
        )
        self.assertTrue(
            category,
            "category_dashboard_farmer missing — dashboard_metrics.xml didn't load",
        )

    def test_dashboard_group_seed_loaded(self):
        """data/dashboards.xml declares the spreadsheet dashboard group."""
        group = self.env.ref(
            "spp_farmer_registry_dashboard.spreadsheet_dashboard_group_farmer",
            raise_if_not_found=False,
        )
        self.assertTrue(
            group,
            "spreadsheet_dashboard_group_farmer missing — dashboards.xml didn't load",
        )

    def test_dashboard_record_seed_loaded(self):
        """data/dashboards.xml declares the farmer overview dashboard."""
        dashboard = self.env.ref(
            "spp_farmer_registry_dashboard.dashboard_farmer_overview",
            raise_if_not_found=False,
        )
        self.assertTrue(
            dashboard,
            "dashboard_farmer_overview missing — dashboards.xml didn't load",
        )
