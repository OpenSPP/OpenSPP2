# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Validation must accept dotted DCI accessors.

The DCI resolver rewrites a dotted cached accessor like ``r.dci.crvs.is_alive``
into ``metric('r.dci.crvs.is_alive', me)`` before the base resolver extracts
identifiers, so ``me`` appears as a bare identifier in the scanned expression.
``validate_expression`` must not report it as an undefined variable.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDCIDottedValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.cel.variable.resolver"]
        # Seeded active ttl variable with a dotted accessor.
        cls.var = cls.env.ref("spp_dci_indicators.var_dci_crvs_is_alive")

    def test_expand_dotted_accessor_does_not_flag_me(self):
        result = self.resolver.expand_expression(
            f"{self.var.cel_accessor} == true", context_type="individual"
        )
        # The accessor was rewritten to a metric() call ...
        self.assertIn(f"metric('{self.var.cel_accessor}', me)", result["expression"])
        # ... and me is not treated as an undefined variable.
        self.assertNotIn("me", result["missing_variables"])

    def test_validate_dotted_accessor_expression_is_valid(self):
        result = self.resolver.validate_expression(
            f"{self.var.cel_accessor} == true", context_type="individual"
        )
        self.assertTrue(
            result["valid"],
            f"dotted DCI accessor should validate; errors: {result['errors']}",
        )
        self.assertNotIn("Undefined variables: me", " ".join(result["errors"]))
