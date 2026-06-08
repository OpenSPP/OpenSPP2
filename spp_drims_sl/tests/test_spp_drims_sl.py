# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Install / data-load sanity tests for spp_drims_sl.

This is a data-only module (Sri Lanka locale configuration for DRIMS) —
it ships seed records but no Python models or methods. The tests below
exercise the install path so CI's per-module coverage matrix has
something to report against, and assert that the headline data records
the rest of the module relies on are actually present after install.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSppDrimsSl(TransactionCase):
    """Spot-check that the seed data declared in __manifest__.py loaded."""

    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_drims_sl")], limit=1)
        self.assertTrue(module, "spp_drims_sl module not registered")
        self.assertEqual(
            module.state,
            "installed",
            f"spp_drims_sl expected 'installed', got {module.state}",
        )

    def test_hazard_category_seed_loaded(self):
        """data/hazard_categories.xml declares at least one category."""
        category = self.env.ref("spp_drims_sl.category_natural", raise_if_not_found=False)
        self.assertTrue(
            category,
            "spp_drims_sl.category_natural missing — hazard_categories.xml didn't load",
        )

    def test_sl_currency_company_config(self):
        """data/company_config.xml activates LKR for the locale."""
        currency = self.env.ref("base.LKR", raise_if_not_found=False)
        self.assertTrue(currency, "base.LKR currency missing")
        self.assertTrue(
            currency.active,
            "LKR currency expected to be active after spp_drims_sl install",
        )
