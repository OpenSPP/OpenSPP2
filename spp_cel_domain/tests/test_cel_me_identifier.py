# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""`me` is a record-root context identifier and must not be flagged as an
undefined variable during validation.

The resolver rewrites cached variables into ``metric('<accessor>', me)`` and
the DCI override rewrites dotted accessors the same way *before* the base
resolver extracts identifiers. ``me`` then appears as a bare identifier in the
scanned expression; unless it is a recognized context identifier,
``validate_expression`` / ``validate_formula_expression`` wrongly report
``Undefined variables: me``.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMeContextIdentifier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resolver = cls.env["spp.cel.variable.resolver"]
        cls.service = cls.env["spp.cel.service"]

    def test_me_is_a_context_identifier(self):
        from odoo.addons.spp_cel_domain.services.cel_parser import CEL_CONTEXT_IDENTIFIERS

        self.assertIn("me", CEL_CONTEXT_IDENTIFIERS)

    def test_expand_does_not_flag_me_as_missing(self):
        result = self.resolver.expand_expression("metric('foo', me) == true")
        self.assertNotIn("me", result["missing_variables"])

    def test_validate_expression_accepts_bare_me(self):
        result = self.resolver.validate_expression("metric('foo', me) == true")
        self.assertTrue(
            result["valid"],
            f"expression with bare me should validate; errors: {result['errors']}",
        )
        self.assertNotIn(
            "Undefined variables: me",
            " ".join(result["errors"]),
        )

    def test_validate_formula_expression_accepts_bare_me(self):
        result = self.service.validate_formula_expression("metric('foo', me)", "individual")
        self.assertNotIn("Missing variables: me", result.get("error") or "")
