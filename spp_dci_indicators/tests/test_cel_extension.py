# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the CEL executor/registry DCI extensions.

cel_extension.py injects the dr/crvs/ibr/sr symbol providers into the
CEL symbol context for partner-based evaluations, and documents those
symbols on the registry_individuals / registry_groups profiles.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# NOTE: CELExecutorDCIExtension._build_symbol_context is intentionally NOT
# tested here. The base spp.cel.executor (a SQL-compilation engine) defines
# no _build_symbol_context method, so the override's super() call raises
# AttributeError and the hook is never invoked during real CEL evaluation.
# This dead/broken executor extension is tracked as a separate architectural
# finding (see the DCI-CEL analysis); writing tests that assert its current
# behaviour would only codify the breakage.


@tagged("post_install", "-at_install")
class TestCELRegistryDCIExtension(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Registry = cls.env["spp.cel.registry"]

    def test_individuals_profile_gets_dci_symbol_docs(self):
        cfg = self.Registry.load_profile("registry_individuals")
        self.assertIn("symbols", cfg)
        for symbol in ("dr", "crvs", "ibr"):
            self.assertIn(symbol, cfg["symbols"])
            self.assertEqual(cfg["symbols"][symbol]["type"], "provider")

    def test_groups_profile_gets_dci_symbol_docs(self):
        cfg = self.Registry.load_profile("registry_groups")
        self.assertIn("symbols", cfg)
        self.assertIn("dr", cfg["symbols"])

    def test_unrelated_profile_not_given_dci_symbols(self):
        """A profile outside the registry_individuals/groups set must not
        gain DCI symbol documentation. Unknown profiles resolve to an
        empty cfg in the base registry, which the DCI extension leaves
        untouched."""
        cfg = self.Registry.load_profile("some_unknown_profile_xyz")
        self.assertNotIn("dr", cfg.get("symbols", {}))

    def test_individuals_profile_symbol_descriptions_present(self):
        cfg = self.Registry.load_profile("registry_individuals")
        self.assertIn("Disability", cfg["symbols"]["dr"]["description"])
        self.assertIn("Civil", cfg["symbols"]["crvs"]["description"])
        self.assertIn("Beneficiary", cfg["symbols"]["ibr"]["description"])
