# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Install / bundle-sanity tests for spp_starter_farmer_registry.

This is a meta-module / bundle — it only declares ``depends`` plus a
single ``ir.config_parameter`` seed. The tests verify that:

- the bundle itself installs cleanly,
- every farmer-registry dependency it bundles is reachable + installed,
- the seed config parameter loaded.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSppStarterFarmerRegistry(TransactionCase):
    """Spot-check that the bundle declared in __manifest__.py installs cleanly."""

    BUNDLE_DEPS = (
        "spp_starter_social_registry",
        "spp_farmer_registry",
        "spp_farmer_registry_vocabularies",
        "spp_land_record",
        "spp_irrigation",
        "spp_gis",
        "spp_programs",
    )

    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_starter_farmer_registry")], limit=1)
        self.assertTrue(module, "spp_starter_farmer_registry not registered")
        self.assertEqual(
            module.state,
            "installed",
            f"spp_starter_farmer_registry expected 'installed', got {module.state}",
        )

    def test_bundle_dependencies_installed(self):
        """Every module in ``depends`` is itself installed."""
        Module = self.env["ir.module.module"]
        for name in self.BUNDLE_DEPS:
            with self.subTest(dep=name):
                module = Module.search([("name", "=", name)], limit=1)
                self.assertTrue(module, f"Bundle dep {name!r} not registered")
                self.assertEqual(
                    module.state,
                    "installed",
                    f"Bundle dep {name!r} expected 'installed', got {module.state}",
                )

    def test_smallholder_threshold_param_loaded(self):
        """data/config_parameters.xml declares the smallholder threshold."""
        param = self.env.ref(
            "spp_starter_farmer_registry.config_smallholder_threshold",
            raise_if_not_found=False,
        )
        self.assertTrue(
            param,
            "config_smallholder_threshold missing — config_parameters.xml didn't load",
        )
