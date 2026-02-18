# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for relational fields (one2many, many2many) used as bare predicates.

When a user writes a CEL expression like `program_membership_ids` (without
a comparison operator), the translator should treat it as a truthiness
check: "has records" → True, "no records" → False. This matches Python
and CEL semantics where non-empty collections are truthy.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRelationalBarePredicates(TransactionCase):
    """Test that one2many and many2many fields work as bare predicates."""

    def setUp(self):
        super().setUp()
        self.service = self.env["spp.cel.service"]

    def test_one2many_field_as_bare_predicate_compiles(self):
        """A one2many field used as a bare predicate should compile.

        Expression like `program_membership_ids` should be treated as
        checking whether the field has records (not empty).
        """
        # program_membership_ids is a One2many on res.partner
        # (from spp_programs module)
        if "program_membership_ids" not in self.env["res.partner"]._fields:
            self.skipTest("spp_programs not installed (no program_membership_ids field)")

        result = self.service.compile_expression(
            "program_membership_ids",
            "registry_groups",
        )
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        # Should produce a domain checking the field is not empty
        self.assertIsInstance(result["domain"], list)

    def test_many2many_field_as_bare_predicate_compiles(self):
        """A many2many field used as a bare predicate should compile."""
        # Find any many2many field on res.partner for testing
        partner_fields = self.env["res.partner"]._fields
        m2m_field = None
        for fname, fobj in partner_fields.items():
            if getattr(fobj, "type", None) == "many2many":
                m2m_field = fname
                break

        if not m2m_field:
            self.skipTest("No many2many field found on res.partner")

        result = self.service.compile_expression(
            m2m_field,
            "registry_groups",
        )
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        self.assertIsInstance(result["domain"], list)

    def test_one2many_predicate_produces_correct_domain(self):
        """Bare one2many predicate should produce a '!= False' domain.

        This is the standard Odoo pattern for checking if a relational
        field has records.
        """
        if "program_membership_ids" not in self.env["res.partner"]._fields:
            self.skipTest("spp_programs not installed (no program_membership_ids field)")

        result = self.service.compile_expression(
            "program_membership_ids",
            "registry_groups",
        )
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")
        # The domain should contain a check for "has records"
        domain = result["domain"]
        # Look for the exact expected leaf in the domain
        expected_leaf = ("program_membership_ids", "!=", False)
        found = any(leaf == expected_leaf for leaf in domain if isinstance(leaf, tuple))
        self.assertTrue(found, f"Expected '{expected_leaf}' to be in domain, but got: {domain}")
