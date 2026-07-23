# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the ``search_registrants`` RPC method.

The administrator-configurable Registry Search controls (``min_chars``,
``result_limit``, targeted search mode) were previously enforced only in the
JavaScript client. These tests pin the server-side enforcement: a caller
invoking the RPC directly must be subject to the same governance as the
portal UI, because the method searches sensitive registrant PII fields
(name, ID number, phone, email).
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSearchRegistrants(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

        cls.alice = cls.Partner.create(
            {
                "name": "Alicia Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.alice_phone = cls.env["spp.phone.number"].create(
            {
                "partner_id": cls.alice.id,
                "phone_no": "09171234567",
            }
        )
        # A pool larger than the admin limit used in the limit tests.
        cls.bulk = cls.Partner.create(
            [
                {
                    "name": f"Bulklimit Person {i:02d}",
                    "is_registrant": True,
                    "is_group": False,
                }
                for i in range(1, 13)
            ]
        )

    def setUp(self):
        super().setUp()
        # Explicit baseline so tests never depend on deployment defaults.
        self.ICP.set_param("spp_registry_search.search_mode", "unified")
        self.ICP.set_param("spp_registry_search.target_field", "name")
        self.ICP.set_param("spp_registry_search.result_limit", "50")
        self.ICP.set_param("spp_registry_search.min_chars", "3")

    def _search(self, term, **kwargs):
        return self.Partner.search_registrants(term, **kwargs)

    # --- min_chars enforcement --------------------------------------------------

    def test_min_chars_enforced_server_side(self):
        """A term shorter than the configured minimum must return nothing,
        even when the RPC is called directly (bypassing the JS check)."""
        self.assertEqual(self._search("Al"), [])

    def test_wildcard_only_term_rejected(self):
        """SQL LIKE wildcards must not count toward min_chars: '%%%' is three
        characters but zero effective characters and would otherwise match
        every registrant."""
        self.assertEqual(self._search("%%%"), [])

    def test_wildcard_padding_does_not_satisfy_min_chars(self):
        """Wildcards mixed with too few literal characters are rejected."""
        self.assertEqual(self._search("Al%"), [])

    def test_min_chars_met_returns_results(self):
        """Regression: a compliant term still finds the registrant."""
        results = self._search("Alicia")
        self.assertIn(self.alice.id, [r["id"] for r in results])

    # --- result limit enforcement ----------------------------------------------

    def test_limit_capped_by_admin_config(self):
        """A caller-supplied limit must never exceed the configured maximum."""
        self.ICP.set_param("spp_registry_search.result_limit", "10")
        results = self._search("Bulklimit", limit=200)
        self.assertLessEqual(len(results), 10)

    def test_lower_caller_limit_honored(self):
        """A caller may request fewer results than the configured maximum."""
        results = self._search("Bulklimit", limit=5)
        self.assertLessEqual(len(results), 5)

    def test_non_numeric_limit_does_not_crash(self):
        """A malformed limit must fall back to the configured limit, not
        raise TypeError (which would surface as a generic 500)."""
        results = self._search("Alicia", limit="not-a-number")
        self.assertIn(self.alice.id, [r["id"] for r in results])

    # --- targeted mode enforcement ----------------------------------------------

    def test_targeted_mode_missing_field_stays_targeted(self):
        """In targeted mode, omitting search_field must NOT fall back to
        unified search over all PII fields; it must use the configured
        default field instead."""
        self.ICP.set_param("spp_registry_search.search_mode", "targeted")
        # Configured field is 'name'; the term only matches via phone.
        self.assertEqual(self._search("09171234567", search_field=None), [])

    def test_targeted_mode_invalid_field_uses_configured_default(self):
        """An unknown search_field falls back to the configured default
        field rather than widening or silently returning nothing."""
        self.ICP.set_param("spp_registry_search.search_mode", "targeted")
        results = self._search("Alicia", search_field="bogus")
        self.assertIn(self.alice.id, [r["id"] for r in results])

    def test_targeted_mode_caller_field_honored(self):
        """Regression: the portal lets users pick a valid field in targeted
        mode; a valid caller-supplied field keeps working."""
        self.ICP.set_param("spp_registry_search.search_mode", "targeted")
        results = self._search("0917123", search_field="phone")
        self.assertIn(self.alice.id, [r["id"] for r in results])

    # --- misc RPC-surface hardening ----------------------------------------------

    def test_non_string_search_term_returns_empty(self):
        """A non-string term must be rejected, not flow into ilike."""
        self.assertEqual(self._search({"weird": "input"}), [])

    def test_search_type_filter_regression(self):
        """Regression: search_type filtering still works."""
        results = self._search("Alicia", search_type="groups")
        self.assertEqual(results, [])
        results = self._search("Alicia", search_type="individuals")
        self.assertIn(self.alice.id, [r["id"] for r in results])
